import re
from pathlib import Path


def apply_compat_patches(build_dir: Path, php_version: str) -> list[str]:
    """Wendet bekannte Kompatibilitäts-Patches auf den PHP-Quellcode an.

    Wird nach dem Entpacken, vor configure/make aufgerufen.
    """
    parts = php_version.split(".")
    major, minor = int(parts[0]), int(parts[1])
    applied: list[str] = []

    if (major, minor) < (8, 0):
        applied.extend(_patch_openssl3_php7x(build_dir))
        applied.extend(_patch_icu_breakiterator_php7x(build_dir))
        applied.extend(_patch_icu_true_false_php7x(build_dir))
        applied.extend(_patch_icu_namespace_php7x(build_dir))
        applied.extend(_patch_icu_breakiterator_class_using(build_dir))
        applied.extend(_patch_icu_convertcpp_h_using(build_dir))
        applied.extend(_patch_icu_codepointiterator_h(build_dir))
        applied.extend(_patch_icu_cpp_using_all(build_dir))
    if major < 7:
        applied.extend(_patch_openssl3_php56(build_dir))

    return applied


def _patch_openssl3_php56(build_dir: Path) -> list[str]:
    """Behebt OpenSSL 3.x-Inkompatibilitäten in ext/openssl/openssl.c für PHP 5.6.

    OpenSSL 1.1+ machte EVP_PKEY, RSA, DSA, DH, X509, EVP_MD_CTX und
    EVP_CIPHER_CTX zu opaken Strukturen. PHP 5.6 greift direkt auf Felder
    zu (pkey->pkey.rsa->n etc.) und alloziert Kontexte auf dem Stack, was
    mit OpenSSL 3.x nicht mehr kompiliert.
    """
    openssl_c = build_dir / "ext" / "openssl" / "openssl.c"
    if not openssl_c.exists():
        return []

    content = openssl_c.read_text()
    if "pbrew openssl3 compat" in content:
        return []

    applied: list[str] = []

    def patch(old: str, new: str) -> bool:
        nonlocal content
        if old in content:
            content = content.replace(old, new)
            return True
        return False

    # ── 1. Compat-Helper-Funktion injizieren ─────────────────────────────────
    # pbrew_bn_to_zval: BigNum-Wert in PHP-Array eintragen (ersetzt OPENSSL_PKEY_GET_BN)
    compat_block = (
        "/* pbrew openssl3 compat: OpenSSL 1.1+ Accessor-Funktionen für PHP 5.6 */\n"
        "#if OPENSSL_VERSION_NUMBER >= 0x10100000L\n"
        "static void pbrew_bn_to_zval(zval *arr, const char *name, const BIGNUM *bn)\n"
        "{\n"
        "\tif (bn != NULL) {\n"
        "\t\tint len = BN_num_bytes(bn);\n"
        "\t\tchar *str = emalloc(len + 1);\n"
        "\t\tBN_bn2bin(bn, (unsigned char*)str);\n"
        "\t\tstr[len] = 0;\n"
        "\t\tadd_assoc_stringl(arr, name, str, len, 0);\n"
        "\t}\n"
        "}\n"
        "#endif\n\n"
    )
    if patch("/* Common */\n#include <time.h>",
             compat_block + "/* Common */\n#include <time.h>"):
        applied.append("openssl: pbrew_bn_to_zval Helper injiziert")

    # ── 2. EVP_dss1 → EVP_sha1 (entfernt in OpenSSL 3.0) ────────────────────
    if patch(
        "\t\tcase OPENSSL_ALGO_DSS1:\n"
        "\t\t\tmdtype = (EVP_MD *) EVP_dss1();\n"
        "\t\t\tbreak;",
        "\t\tcase OPENSSL_ALGO_DSS1:\n"
        "\t\t\tmdtype = (EVP_MD *) EVP_sha1();\n"
        "\t\t\tbreak;",
    ):
        applied.append("openssl: EVP_dss1() → EVP_sha1() (OpenSSL 3.0)")

    # ── X509 / extension Struct-Zugriffe ─────────────────────────────────────
    if patch(
        "\tp = extension->value->data;\n\tlength = extension->value->length;",
        "\t{\n"
        "\t\tASN1_STRING *_ext_asn = X509_EXTENSION_get_data(extension);\n"
        "\t\tp = ASN1_STRING_get0_data(_ext_asn);\n"
        "\t\tlength = ASN1_STRING_length(_ext_asn);\n"
        "\t}",
    ):
        applied.append("openssl: extension->value → X509_EXTENSION_get_data/ASN1_STRING_get0_data")

    if patch(
        '\tif (cert->name) {\n\t\tadd_assoc_string(return_value, "name", cert->name, 1);\n\t}',
        '\t{\n'
        '\t\tchar *_cert_name = X509_NAME_oneline(X509_get_subject_name(cert), NULL, 0);\n'
        '\t\tif (_cert_name) {\n'
        '\t\t\tadd_assoc_string(return_value, "name", _cert_name, 1);\n'
        '\t\t\tOPENSSL_free(_cert_name);\n'
        '\t\t}\n'
        '\t}',
    ):
        applied.append("openssl: cert->name → X509_NAME_oneline(X509_get_subject_name(cert))")

    if patch(
        "sig_nid = OBJ_obj2nid((cert)->sig_alg->algorithm);",
        "sig_nid = X509_get_signature_nid(cert);",
    ):
        applied.append("openssl: cert->sig_alg->algorithm → X509_get_signature_nid")

    # ── 3. pkey->type / key->type → EVP_PKEY_base_id (alle switch-Stellen) ────
    # Regex statt Literal: PHP 5.6 nutzt `pkey` und `key` als Variablennamen
    _before_type = content
    content = content.replace("switch (pkey->type)", "switch (EVP_PKEY_base_id(pkey))")
    content = re.sub(r'EVP_PKEY_type\((\w+)->type\)', r'EVP_PKEY_base_id(\1)', content)
    if content != _before_type:
        applied.append("openssl: pkey->type / key->type → EVP_PKEY_base_id")

    # ── 4. php_openssl_is_private_key: RSA/DSA/DH Struct-Felder ─────────────
    # Achtung: Step 3 hat pkey->type bereits ersetzt; old-String nutzt EVP_PKEY_base_id
    patch(
        "\tswitch (EVP_PKEY_base_id(pkey)) {\n"
        "#ifndef NO_RSA\n"
        "\t\tcase EVP_PKEY_RSA:\n"
        "\t\tcase EVP_PKEY_RSA2:\n"
        "\t\t\tassert(pkey->pkey.rsa != NULL);\n"
        "\t\t\tif (pkey->pkey.rsa != NULL && (NULL == pkey->pkey.rsa->p || NULL == pkey->pkey.rsa->q)) {\n"
        "\t\t\t\treturn 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "#endif\n"
        "#ifndef NO_DSA\n"
        "\t\tcase EVP_PKEY_DSA:\n"
        "\t\tcase EVP_PKEY_DSA1:\n"
        "\t\tcase EVP_PKEY_DSA2:\n"
        "\t\tcase EVP_PKEY_DSA3:\n"
        "\t\tcase EVP_PKEY_DSA4:\n"
        "\t\t\tassert(pkey->pkey.dsa != NULL);\n\n"
        "\t\t\tif (NULL == pkey->pkey.dsa->p || NULL == pkey->pkey.dsa->q || NULL == pkey->pkey.dsa->priv_key){ \n"
        "\t\t\t\treturn 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "#endif\n"
        "#ifndef NO_DH\n"
        "\t\tcase EVP_PKEY_DH:\n"
        "\t\t\tassert(pkey->pkey.dh != NULL);\n\n"
        "\t\t\tif (NULL == pkey->pkey.dh->p || NULL == pkey->pkey.dh->priv_key) {\n"
        "\t\t\t\treturn 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "#endif\n"
        "#ifdef HAVE_EVP_PKEY_EC\n"
        "\t\tcase EVP_PKEY_EC:\n"
        "\t\t\tassert(pkey->pkey.ec != NULL);\n\n"
        "\t\t\tif ( NULL == EC_KEY_get0_private_key(pkey->pkey.ec)) {\n"
        "\t\t\t\treturn 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "#endif",
        "\tswitch (EVP_PKEY_base_id(pkey)) {\n"
        "#ifndef NO_RSA\n"
        "\t\tcase EVP_PKEY_RSA:\n"
        "\t\tcase EVP_PKEY_RSA2: {\n"
        "\t\t\tRSA *_rsa = EVP_PKEY_get0_RSA(pkey);\n"
        "\t\t\tassert(_rsa != NULL);\n"
        "\t\t\tif (_rsa != NULL) {\n"
        "\t\t\t\tconst BIGNUM *_p = NULL, *_q = NULL;\n"
        "\t\t\t\tRSA_get0_factors(_rsa, &_p, &_q);\n"
        "\t\t\t\tif (_p == NULL || _q == NULL) return 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "\t\t}\n"
        "#endif\n"
        "#ifndef NO_DSA\n"
        "\t\tcase EVP_PKEY_DSA:\n"
        "\t\tcase EVP_PKEY_DSA1:\n"
        "\t\tcase EVP_PKEY_DSA2:\n"
        "\t\tcase EVP_PKEY_DSA3:\n"
        "\t\tcase EVP_PKEY_DSA4: {\n"
        "\t\t\tDSA *_dsa = EVP_PKEY_get0_DSA(pkey);\n"
        "\t\t\tassert(_dsa != NULL);\n"
        "\t\t\tif (_dsa != NULL) {\n"
        "\t\t\t\tconst BIGNUM *_p = NULL, *_q = NULL, *_g = NULL, *_pub = NULL, *_priv = NULL;\n"
        "\t\t\t\tDSA_get0_pqg(_dsa, &_p, &_q, &_g);\n"
        "\t\t\t\tDSA_get0_key(_dsa, &_pub, &_priv);\n"
        "\t\t\t\tif (_p == NULL || _q == NULL || _priv == NULL) return 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "\t\t}\n"
        "#endif\n"
        "#ifndef NO_DH\n"
        "\t\tcase EVP_PKEY_DH: {\n"
        "\t\t\tDH *_dh = EVP_PKEY_get0_DH(pkey);\n"
        "\t\t\tassert(_dh != NULL);\n"
        "\t\t\tif (_dh != NULL) {\n"
        "\t\t\t\tconst BIGNUM *_p = NULL, *_q = NULL, *_g = NULL, *_pub = NULL, *_priv = NULL;\n"
        "\t\t\t\tDH_get0_pqg(_dh, &_p, &_q, &_g);\n"
        "\t\t\t\tDH_get0_key(_dh, &_pub, &_priv);\n"
        "\t\t\t\tif (_p == NULL || _priv == NULL) return 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "\t\t}\n"
        "#endif\n"
        "#ifdef HAVE_EVP_PKEY_EC\n"
        "\t\tcase EVP_PKEY_EC: {\n"
        "\t\t\tEC_KEY *_ec = EVP_PKEY_get0_EC_KEY(pkey);\n"
        "\t\t\tassert(_ec != NULL);\n"
        "\t\t\tif (_ec != NULL && EC_KEY_get0_private_key(_ec) == NULL) {\n"
        "\t\t\t\treturn 0;\n"
        "\t\t\t}\n"
        "\t\t\tbreak;\n"
        "\t\t}\n"
        "#endif",
    )
    # Note: may already be patched by step 3 (EVP_PKEY_base_id), that's fine

    # ── 5. php_openssl_pkey_init_dsa: DSA Struct-Felder ──────────────────────
    patch(
        "zend_bool php_openssl_pkey_init_dsa(DSA *dsa)\n"
        "{\n"
        "\tif (!dsa->p || !dsa->q || !dsa->g) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\tif (dsa->priv_key || dsa->pub_key) {\n"
        "\t\treturn 1;\n"
        "\t}\n"
        "\tPHP_OPENSSL_RAND_ADD_TIME();\n"
        "\tif (!DSA_generate_key(dsa)) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\t/* if BN_mod_exp return -1, then DSA_generate_key succeed for failed key\n"
        "\t * so we need to double check that public key is created */\n"
        "\tif (!dsa->pub_key || BN_is_zero(dsa->pub_key)) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\t/* all good */\n"
        "\treturn 1;\n"
        "}",
        "zend_bool php_openssl_pkey_init_dsa(DSA *dsa)\n"
        "{\n"
        "\tconst BIGNUM *p = NULL, *q = NULL, *g = NULL, *pub_key = NULL, *priv_key = NULL;\n"
        "\tDSA_get0_pqg(dsa, &p, &q, &g);\n"
        "\tDSA_get0_key(dsa, &pub_key, &priv_key);\n"
        "\tif (!p || !q || !g) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\tif (priv_key || pub_key) {\n"
        "\t\treturn 1;\n"
        "\t}\n"
        "\tPHP_OPENSSL_RAND_ADD_TIME();\n"
        "\tif (!DSA_generate_key(dsa)) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\tDSA_get0_key(dsa, &pub_key, &priv_key);\n"
        "\tif (!pub_key || BN_is_zero(pub_key)) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\treturn 1;\n"
        "}",
    )

    # ── 6. php_openssl_pkey_init_dh: DH Struct-Felder ────────────────────────
    patch(
        "zend_bool php_openssl_pkey_init_dh(DH *dh)\n"
        "{\n"
        "\tif (!dh->p || !dh->g) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\tif (dh->pub_key) {\n"
        "\t\treturn 1;\n"
        "\t}\n"
        "\tPHP_OPENSSL_RAND_ADD_TIME();\n"
        "\tif (!DH_generate_key(dh)) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\t/* all good */\n"
        "\treturn 1;\n"
        "}",
        "zend_bool php_openssl_pkey_init_dh(DH *dh)\n"
        "{\n"
        "\tconst BIGNUM *p = NULL, *q = NULL, *g = NULL, *pub_key = NULL, *priv_key = NULL;\n"
        "\tDH_get0_pqg(dh, &p, &q, &g);\n"
        "\tDH_get0_key(dh, &pub_key, &priv_key);\n"
        "\tif (!p || !g) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\tif (pub_key) {\n"
        "\t\treturn 1;\n"
        "\t}\n"
        "\tPHP_OPENSSL_RAND_ADD_TIME();\n"
        "\tif (!DH_generate_key(dh)) {\n"
        "\t\treturn 0;\n"
        "\t}\n"
        "\treturn 1;\n"
        "}",
    )

    # ── 7. OPENSSL_PKEY_GET_BN / OPENSSL_PKEY_SET_BN Makros ─────────────────
    # GET_BN: greift auf pkey->pkey._type->_name zu (opak in OpenSSL 3.x)
    patch(
        "#define OPENSSL_PKEY_GET_BN(_type, _name) do {\t\t\t\t\t\t\t\\\n"
        "\t\tif (pkey->pkey._type->_name != NULL) {\t\t\t\t\t\t\t\\\n"
        "\t\t\tint len = BN_num_bytes(pkey->pkey._type->_name);\t\t\t\\\n"
        "\t\t\tchar *str = emalloc(len + 1);\t\t\t\t\t\t\t\t\\\n"
        "\t\t\tBN_bn2bin(pkey->pkey._type->_name, (unsigned char*)str);\t\\\n"
        "\t\t\tstr[len] = 0;                                           \t\\\n"
        "\t\t\tadd_assoc_stringl(_type, #_name, str, len, 0);\t\t\t\t\\\n"
        "\t\t}\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\\\n"
        "\t} while (0)",
        "/* pbrew: OPENSSL_PKEY_GET_BN ersetzt durch pbrew_bn_to_zval-Aufrufe unten */\n"
        "#define OPENSSL_PKEY_GET_BN(_type, _name) ((void)0)",
    )

    # SET_BN: setzt _type->_name = BN_bin2bn(...) direkt (opak in OpenSSL 3.x)
    patch(
        "#define OPENSSL_PKEY_SET_BN(_ht, _type, _name) do {\t\t\t\t\t\t\\\n"
        "\t\tzval **bn;\t\t\t\t\t\t\t\t\t\t\t\t\t\t\\\n"
        "\t\tif (zend_hash_find(_ht, #_name, sizeof(#_name),\t(void**)&bn) == SUCCESS && \\\n"
        "\t\t\t\tZ_TYPE_PP(bn) == IS_STRING) {\t\t\t\t\t\t\t\\\n"
        "\t\t\t_type->_name = BN_bin2bn(\t\t\t\t\t\t\t\t\t\\\n"
        "\t\t\t\t(unsigned char*)Z_STRVAL_PP(bn),\t\t\t\t\t\t\\\n"
        "\t \t\t\tZ_STRLEN_PP(bn), NULL);\t\t\t\t\t\t\t\t\t\\\n"
        "\t    }                                                               \\\n"
        "\t} while (0);",
        "/* pbrew: OPENSSL_PKEY_SET_BN ersetzt durch RSA/DSA/DH_set0_*-Aufrufe unten */\n"
        "#define OPENSSL_PKEY_SET_BN(_ht, _type, _name) ((void)0)",
    )

    # ── 8. openssl_pkey_new: RSA-Block mit RSA_set0_* ────────────────────────
    patch(
        "\t\t\t\tRSA *rsa = RSA_new();\n"
        "\t\t\t\tif (rsa) {\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, n);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, e);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, d);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, p);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, q);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, dmp1);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, dmq1);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), rsa, iqmp);\n"
        "\t\t\t\t\tif (rsa->n && rsa->d) {\n"
        "\t\t\t\t\t\tif (EVP_PKEY_assign_RSA(pkey, rsa)) {\n"
        "\t\t\t\t\t\t\tRETURN_RESOURCE(zend_list_insert(pkey, le_key TSRMLS_CC));\n"
        "\t\t\t\t\t\t}\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t\tRSA_free(rsa);\n"
        "\t\t\t\t}",
        "\t\t\t\tRSA *rsa = RSA_new();\n"
        "\t\t\t\tif (rsa) {\n"
        "\t\t\t\t\tBIGNUM *n=NULL,*e=NULL,*d=NULL,*p=NULL,*q=NULL,*dmp1=NULL,*dmq1=NULL,*iqmp=NULL;\n"
        "\t\t\t\t\tzval **_bn;\n"
        "\t\t\t\t\t#define _PBREW_LOAD_BN(_f) do { if (zend_hash_find(Z_ARRVAL_PP(data),\\\n"
        "\t\t\t\t\t\t#_f,sizeof(#_f),(void**)&_bn)==SUCCESS&&Z_TYPE_PP(_bn)==IS_STRING)\\\n"
        "\t\t\t\t\t\t_f=BN_bin2bn((unsigned char*)Z_STRVAL_PP(_bn),Z_STRLEN_PP(_bn),NULL);\\\n"
        "\t\t\t\t\t} while(0)\n"
        "\t\t\t\t\t_PBREW_LOAD_BN(n); _PBREW_LOAD_BN(e); _PBREW_LOAD_BN(d);\n"
        "\t\t\t\t\t_PBREW_LOAD_BN(p); _PBREW_LOAD_BN(q);\n"
        "\t\t\t\t\t_PBREW_LOAD_BN(dmp1); _PBREW_LOAD_BN(dmq1); _PBREW_LOAD_BN(iqmp);\n"
        "\t\t\t\t\t#undef _PBREW_LOAD_BN\n"
        "\t\t\t\t\tif (n && d) {\n"
        "\t\t\t\t\t\tRSA_set0_key(rsa, n, e, d); n=e=d=NULL;\n"
        "\t\t\t\t\t\tif (p && q) { RSA_set0_factors(rsa, p, q); p=q=NULL; }\n"
        "\t\t\t\t\t\tif (dmp1&&dmq1&&iqmp) { RSA_set0_crt_params(rsa,dmp1,dmq1,iqmp); dmp1=dmq1=iqmp=NULL; }\n"
        "\t\t\t\t\t\tif (EVP_PKEY_assign_RSA(pkey, rsa)) {\n"
        "\t\t\t\t\t\t\tRETURN_RESOURCE(zend_list_insert(pkey, le_key TSRMLS_CC));\n"
        "\t\t\t\t\t\t}\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t\tBN_free(n); BN_free(e); BN_free(d);\n"
        "\t\t\t\t\tBN_free(p); BN_free(q);\n"
        "\t\t\t\t\tBN_free(dmp1); BN_free(dmq1); BN_free(iqmp);\n"
        "\t\t\t\t\tRSA_free(rsa);\n"
        "\t\t\t\t}",
    )

    # ── 9. openssl_pkey_new: DSA-Block mit DSA_set0_* ────────────────────────
    patch(
        "\t\t\t\tDSA *dsa = DSA_new();\n"
        "\t\t\t\tif (dsa) {\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dsa, p);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dsa, q);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dsa, g);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dsa, priv_key);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dsa, pub_key);\n"
        "\t\t\t\t\tif (php_openssl_pkey_init_dsa(dsa)) {\n"
        "\t\t\t\t\t\tif (EVP_PKEY_assign_DSA(pkey, dsa)) {\n"
        "\t\t\t\t\t\t\tRETURN_RESOURCE(zend_list_insert(pkey, le_key TSRMLS_CC));\n"
        "\t\t\t\t\t\t}\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t\tDSA_free(dsa);\n"
        "\t\t\t\t}",
        "\t\t\t\tDSA *dsa = DSA_new();\n"
        "\t\t\t\tif (dsa) {\n"
        "\t\t\t\t\tBIGNUM *p=NULL,*q=NULL,*g=NULL,*pub_key=NULL,*priv_key=NULL;\n"
        "\t\t\t\t\tzval **_bn;\n"
        "\t\t\t\t\t#define _PBREW_LOAD_BN(_f) do { if (zend_hash_find(Z_ARRVAL_PP(data),\\\n"
        "\t\t\t\t\t\t#_f,sizeof(#_f),(void**)&_bn)==SUCCESS&&Z_TYPE_PP(_bn)==IS_STRING)\\\n"
        "\t\t\t\t\t\t_f=BN_bin2bn((unsigned char*)Z_STRVAL_PP(_bn),Z_STRLEN_PP(_bn),NULL);\\\n"
        "\t\t\t\t\t} while(0)\n"
        "\t\t\t\t\t_PBREW_LOAD_BN(p); _PBREW_LOAD_BN(q); _PBREW_LOAD_BN(g);\n"
        "\t\t\t\t\t_PBREW_LOAD_BN(priv_key); _PBREW_LOAD_BN(pub_key);\n"
        "\t\t\t\t\t#undef _PBREW_LOAD_BN\n"
        "\t\t\t\t\tDSA_set0_pqg(dsa, p, q, g);\n"
        "\t\t\t\t\tDSA_set0_key(dsa, pub_key, priv_key);\n"
        "\t\t\t\t\tif (php_openssl_pkey_init_dsa(dsa)) {\n"
        "\t\t\t\t\t\tif (EVP_PKEY_assign_DSA(pkey, dsa)) {\n"
        "\t\t\t\t\t\t\tRETURN_RESOURCE(zend_list_insert(pkey, le_key TSRMLS_CC));\n"
        "\t\t\t\t\t\t}\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t\tDSA_free(dsa);\n"
        "\t\t\t\t}",
    )

    # ── 10. openssl_pkey_new: DH-Block mit DH_set0_* ─────────────────────────
    patch(
        "\t\t\t\tDH *dh = DH_new();\n"
        "\t\t\t\tif (dh) {\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dh, p);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dh, g);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dh, priv_key);\n"
        "\t\t\t\t\tOPENSSL_PKEY_SET_BN(Z_ARRVAL_PP(data), dh, pub_key);\n"
        "\t\t\t\t\tif (php_openssl_pkey_init_dh(dh)) {\n"
        "\t\t\t\t\t\tif (EVP_PKEY_assign_DH(pkey, dh)) {\n"
        "\t\t\t\t\t\t\tRETURN_RESOURCE(zend_list_insert(pkey, le_key TSRMLS_CC));\n"
        "\t\t\t\t\t\t}\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t\tDH_free(dh);\n"
        "\t\t\t\t}",
        "\t\t\t\tDH *dh = DH_new();\n"
        "\t\t\t\tif (dh) {\n"
        "\t\t\t\t\tBIGNUM *p=NULL,*q=NULL,*g=NULL,*pub_key=NULL,*priv_key=NULL;\n"
        "\t\t\t\t\tzval **_bn;\n"
        "\t\t\t\t\t#define _PBREW_LOAD_BN(_f) do { if (zend_hash_find(Z_ARRVAL_PP(data),\\\n"
        "\t\t\t\t\t\t#_f,sizeof(#_f),(void**)&_bn)==SUCCESS&&Z_TYPE_PP(_bn)==IS_STRING)\\\n"
        "\t\t\t\t\t\t_f=BN_bin2bn((unsigned char*)Z_STRVAL_PP(_bn),Z_STRLEN_PP(_bn),NULL);\\\n"
        "\t\t\t\t\t} while(0)\n"
        "\t\t\t\t\t_PBREW_LOAD_BN(p); _PBREW_LOAD_BN(g);\n"
        "\t\t\t\t\t_PBREW_LOAD_BN(priv_key); _PBREW_LOAD_BN(pub_key);\n"
        "\t\t\t\t\t#undef _PBREW_LOAD_BN\n"
        "\t\t\t\t\tDH_set0_pqg(dh, p, NULL, g);\n"
        "\t\t\t\t\tDH_set0_key(dh, pub_key, priv_key);\n"
        "\t\t\t\t\tif (php_openssl_pkey_init_dh(dh)) {\n"
        "\t\t\t\t\t\tif (EVP_PKEY_assign_DH(pkey, dh)) {\n"
        "\t\t\t\t\t\t\tRETURN_RESOURCE(zend_list_insert(pkey, le_key TSRMLS_CC));\n"
        "\t\t\t\t\t\t}\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t\tDH_free(dh);\n"
        "\t\t\t\t}",
    )

    # ── 11. openssl_pkey_get_details: RSA-Block mit RSA_get0_* ───────────────
    patch(
        "\t\t\tif (pkey->pkey.rsa != NULL) {\n"
        "\t\t\t\tzval *rsa;\n\n"
        "\t\t\t\tALLOC_INIT_ZVAL(rsa);\n"
        "\t\t\t\tarray_init(rsa);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, n);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, e);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, d);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, p);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, q);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, dmp1);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, dmq1);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(rsa, iqmp);\n"
        "\t\t\t\tadd_assoc_zval(return_value, \"rsa\", rsa);\n"
        "\t\t\t}",
        "\t\t\t{\n"
        "\t\t\t\t\tRSA *_rsa = EVP_PKEY_get0_RSA(pkey);\n"
        "\t\t\t\t\tif (_rsa != NULL) {\n"
        "\t\t\t\t\t\tconst BIGNUM *n,*e,*d,*p,*q,*dmp1,*dmq1,*iqmp;\n"
        "\t\t\t\t\t\tzval *rsa;\n"
        "\t\t\t\t\t\tRSA_get0_key(_rsa, &n, &e, &d);\n"
        "\t\t\t\t\t\tRSA_get0_factors(_rsa, &p, &q);\n"
        "\t\t\t\t\t\tRSA_get0_crt_params(_rsa, &dmp1, &dmq1, &iqmp);\n"
        "\t\t\t\t\t\tALLOC_INIT_ZVAL(rsa);\n"
        "\t\t\t\t\t\tarray_init(rsa);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"n\", n);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"e\", e);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"d\", d);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"p\", p);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"q\", q);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"dmp1\", dmp1);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"dmq1\", dmq1);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(rsa, \"iqmp\", iqmp);\n"
        "\t\t\t\t\t\tadd_assoc_zval(return_value, \"rsa\", rsa);\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t}",
    )

    # ── 12. openssl_pkey_get_details: DSA-Block mit DSA_get0_* ───────────────
    patch(
        "\t\t\tif (pkey->pkey.dsa != NULL) {\n"
        "\t\t\t\tzval *dsa;\n\n"
        "\t\t\t\tALLOC_INIT_ZVAL(dsa);\n"
        "\t\t\t\tarray_init(dsa);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dsa, p);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dsa, q);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dsa, g);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dsa, priv_key);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dsa, pub_key);\n"
        "\t\t\t\tadd_assoc_zval(return_value, \"dsa\", dsa);\n"
        "\t\t\t}",
        "\t\t\t{\n"
        "\t\t\t\t\tDSA *_dsa = EVP_PKEY_get0_DSA(pkey);\n"
        "\t\t\t\t\tif (_dsa != NULL) {\n"
        "\t\t\t\t\t\tconst BIGNUM *p, *q, *g, *pub_key, *priv_key;\n"
        "\t\t\t\t\t\tzval *dsa;\n"
        "\t\t\t\t\t\tDSA_get0_pqg(_dsa, &p, &q, &g);\n"
        "\t\t\t\t\t\tDSA_get0_key(_dsa, &pub_key, &priv_key);\n"
        "\t\t\t\t\t\tALLOC_INIT_ZVAL(dsa);\n"
        "\t\t\t\t\t\tarray_init(dsa);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dsa, \"p\", p);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dsa, \"q\", q);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dsa, \"g\", g);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dsa, \"priv_key\", priv_key);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dsa, \"pub_key\", pub_key);\n"
        "\t\t\t\t\t\tadd_assoc_zval(return_value, \"dsa\", dsa);\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t}",
    )

    # ── 13. openssl_pkey_get_details: DH-Block mit DH_get0_* ─────────────────
    patch(
        "\t\t\tif (pkey->pkey.dh != NULL) {\n"
        "\t\t\t\tzval *dh;\n\n"
        "\t\t\t\tALLOC_INIT_ZVAL(dh);\n"
        "\t\t\t\tarray_init(dh);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dh, p);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dh, g);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dh, priv_key);\n"
        "\t\t\t\tOPENSSL_PKEY_GET_BN(dh, pub_key);\n"
        "\t\t\t\tadd_assoc_zval(return_value, \"dh\", dh);\n"
        "\t\t\t}",
        "\t\t\t{\n"
        "\t\t\t\t\tDH *_dh = EVP_PKEY_get0_DH(pkey);\n"
        "\t\t\t\t\tif (_dh != NULL) {\n"
        "\t\t\t\t\t\tconst BIGNUM *p, *q, *g, *pub_key, *priv_key;\n"
        "\t\t\t\t\t\tzval *dh;\n"
        "\t\t\t\t\t\tDH_get0_pqg(_dh, &p, &q, &g);\n"
        "\t\t\t\t\t\tDH_get0_key(_dh, &pub_key, &priv_key);\n"
        "\t\t\t\t\t\tALLOC_INIT_ZVAL(dh);\n"
        "\t\t\t\t\t\tarray_init(dh);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dh, \"p\", p);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dh, \"g\", g);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dh, \"priv_key\", priv_key);\n"
        "\t\t\t\t\t\tpbrew_bn_to_zval(dh, \"pub_key\", pub_key);\n"
        "\t\t\t\t\t\tadd_assoc_zval(return_value, \"dh\", dh);\n"
        "\t\t\t\t\t}\n"
        "\t\t\t\t}",
    )

    # ── 14. pkey->pkey.rsa/dh/ec in encrypt/decrypt/compute_key ─────────────
    # Nach den Makro-Blöcken und is_private_key sind diese einfache Ersetzungen
    for old_field, new_call in [
        ("pkey->pkey.rsa", "EVP_PKEY_get0_RSA(pkey)"),
        ("pkey->pkey.dsa", "EVP_PKEY_get0_DSA(pkey)"),
        ("pkey->pkey.dh",  "EVP_PKEY_get0_DH(pkey)"),
        ("pkey->pkey.ec",  "EVP_PKEY_get0_EC_KEY(pkey)"),
    ]:
        if old_field in content:
            content = content.replace(old_field, new_call)
            applied.append(f"openssl: {old_field} → {new_call}")

    # ── 15. EVP_MD_CTX Stack → Heap ──────────────────────────────────────────
    _before_evp = content
    content = content.replace("\tEVP_MD_CTX md_ctx;\n", "\tEVP_MD_CTX *md_ctx = EVP_MD_CTX_new();\n")
    content = content.replace("\tEVP_MD_CTX     md_ctx;\n", "\tEVP_MD_CTX *md_ctx = EVP_MD_CTX_new();\n")
    content = content.replace("EVP_MD_CTX_cleanup(&md_ctx)", "EVP_MD_CTX_free(md_ctx)")
    # Ersetze alle &md_ctx-Aufrufe unabhängig von Leerzeichen (Regex statt Literal-Spacing)
    content = re.sub(r'\(&md_ctx\b', '(md_ctx', content)
    if content != _before_evp:
        applied.append("openssl: EVP_MD_CTX Stack→Heap, cleanup→free")

    # ── 16. EVP_CIPHER_CTX Stack → Heap (mit EVP_CIPHER_CTX_reset) ───────────
    _before_cipher = content
    content = content.replace("\tEVP_CIPHER_CTX ctx;\n", "\tEVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();\n")
    content = content.replace("\tEVP_CIPHER_CTX cipher_ctx;\n", "\tEVP_CIPHER_CTX *cipher_ctx = EVP_CIPHER_CTX_new();\n")
    content = content.replace("EVP_CIPHER_CTX_cleanup(&ctx)", "EVP_CIPHER_CTX_reset(ctx)")
    content = content.replace("EVP_CIPHER_CTX_cleanup(&cipher_ctx)", "EVP_CIPHER_CTX_reset(cipher_ctx)")
    content = content.replace(" \tEVP_CIPHER_CTX_cleanup(&cipher_ctx)", "\tEVP_CIPHER_CTX_reset(cipher_ctx)")
    for fn_call in [
        "EVP_EncryptInit(&ctx,", "EVP_SealInit(&ctx,", "EVP_SealUpdate(&ctx,",
        "EVP_SealFinal(&ctx,",   "EVP_OpenInit(&ctx,", "EVP_OpenUpdate(&ctx,",
        "EVP_OpenFinal(&ctx,",   "EVP_CIPHER_CTX_iv_length(&ctx)", "EVP_CIPHER_CTX_block_size(&ctx)",
    ]:
        content = content.replace(fn_call, fn_call.replace("(&ctx", "(ctx"))
    for fn_call in [
        "EVP_EncryptInit(&cipher_ctx,", "EVP_EncryptInit_ex(&cipher_ctx,",
        "EVP_EncryptUpdate(&cipher_ctx,", "EVP_EncryptFinal(&cipher_ctx,",
        "EVP_DecryptInit(&cipher_ctx,", "EVP_DecryptInit_ex(&cipher_ctx,",
        "EVP_DecryptUpdate(&cipher_ctx,", "EVP_DecryptFinal(&cipher_ctx,",
        "EVP_CIPHER_CTX_set_key_length(&cipher_ctx,", "EVP_CIPHER_CTX_set_padding(&cipher_ctx,",
    ]:
        content = content.replace(fn_call, fn_call.replace("(&cipher_ctx,", "(cipher_ctx,"))
    # EVP_CIPHER_CTX_free am Funktionsende: letzten reset → free
    patch(
        "\tefree(key_resources);\n}\n/* }}} */\n\n/* {{{ proto bool openssl_open",
        "\tefree(key_resources);\n\tEVP_CIPHER_CTX_free(ctx);\n}\n/* }}} */\n\n/* {{{ proto bool openssl_open",
    )
    patch(
        "\tEVP_CIPHER_CTX_reset(ctx);\n}\n/* }}} */\n\n\nstatic void openssl_add_method_or_alias",
        "\tEVP_CIPHER_CTX_free(ctx);\n}\n/* }}} */\n\n\nstatic void openssl_add_method_or_alias",
    )
    patch(
        "\tEVP_CIPHER_CTX_reset(cipher_ctx);\n}\n/* }}} */\n\n/* {{{ proto string openssl_decrypt",
        "\tEVP_CIPHER_CTX_free(cipher_ctx);\n}\n/* }}} */\n\n/* {{{ proto string openssl_decrypt",
    )
    patch(
        "\tEVP_CIPHER_CTX_reset(cipher_ctx);\n}\n/* }}} */\n\n/* {{{ proto int openssl_cipher_iv_length",
        "\tEVP_CIPHER_CTX_free(cipher_ctx);\n}\n/* }}} */\n\n/* {{{ proto int openssl_cipher_iv_length",
    )
    if content != _before_cipher:
        applied.append("openssl: EVP_CIPHER_CTX Stack→Heap, reset+free")

    if content != openssl_c.read_text():
        openssl_c.write_text(content)

    # ── ext/openssl/xp_ssl.c: SSLv2 Guard für OpenSSL 1.1+ ──────────────────
    # SSLv2_client/server_method() existiert nicht mehr in OpenSSL 1.1+.
    # Der bestehende #ifndef OPENSSL_NO_SSL2 guard greift in OpenSSL 3.x nicht.
    xp_ssl = build_dir / "ext" / "openssl" / "xp_ssl.c"
    if xp_ssl.exists():
        xp = xp_ssl.read_text()
        xp_new = xp.replace(
            "\tif (method_value == STREAM_CRYPTO_METHOD_SSLv2) {\n"
            "#ifndef OPENSSL_NO_SSL2\n"
            "\t\treturn is_client ? SSLv2_client_method() : SSLv2_server_method();\n",
            "\tif (method_value == STREAM_CRYPTO_METHOD_SSLv2) {\n"
            "#if !defined(OPENSSL_NO_SSL2) && OPENSSL_VERSION_NUMBER < 0x10100000L\n"
            "\t\treturn is_client ? SSLv2_client_method() : SSLv2_server_method();\n",
        )
        if xp_new != xp:
            xp_ssl.write_text(xp_new)
            applied.append("openssl: SSLv2_*_method guard für OpenSSL 1.1+ (xp_ssl.c)")

    # ── ext/phar/util.c: EVP_MD_CTX Stack→Heap ──────────────────────────────
    phar_util = build_dir / "ext" / "phar" / "util.c"
    if phar_util.exists():
        phar = phar_util.read_text()
        _before_phar = phar
        phar = phar.replace("\t\t\tEVP_MD_CTX md_ctx;\n", "\t\t\tEVP_MD_CTX *md_ctx = EVP_MD_CTX_new();\n")
        phar = phar.replace("EVP_VerifyInit(&md_ctx,", "EVP_VerifyInit(md_ctx,")
        phar = phar.replace("EVP_VerifyUpdate (&md_ctx,", "EVP_VerifyUpdate(md_ctx,")
        phar = phar.replace("EVP_VerifyFinal(&md_ctx,", "EVP_VerifyFinal(md_ctx,")
        phar = phar.replace("EVP_MD_CTX_cleanup(&md_ctx)", "EVP_MD_CTX_free(md_ctx)")
        if phar != _before_phar:
            phar_util.write_text(phar)
            applied.append("phar: EVP_MD_CTX Stack→Heap, cleanup→free (util.c)")

    if applied:
        applied.insert(0, "openssl: OpenSSL 3.x-Patches für PHP 5.6 angewendet")
    return applied


def _patch_openssl3_php7x(build_dir: Path) -> list[str]:
    """Behebt RSA_SSLV23_PADDING-Kompilierungsfehler mit OpenSSL 3.x.

    RSA_SSLV23_PADDING wurde in OpenSSL 3.0 entfernt. Die PHP-Konstante
    OPENSSL_SSLV23_PADDING wird nur noch registriert wenn der Header sie kennt.
    """
    openssl_c = build_dir / "ext" / "openssl" / "openssl.c"
    if not openssl_c.exists():
        return []

    old = (
        '\tREGISTER_LONG_CONSTANT("OPENSSL_SSLV23_PADDING", '
        'RSA_SSLV23_PADDING, CONST_CS|CONST_PERSISTENT);'
    )
    new = (
        '#ifdef RSA_SSLV23_PADDING\n'
        '\tREGISTER_LONG_CONSTANT("OPENSSL_SSLV23_PADDING", '
        'RSA_SSLV23_PADDING, CONST_CS|CONST_PERSISTENT);\n'
        '#endif'
    )

    content = openssl_c.read_text()
    if new in content or old not in content:
        return []

    openssl_c.write_text(content.replace(old, new))
    return ["openssl: RSA_SSLV23_PADDING guard für OpenSSL 3.x"]


def _patch_icu_breakiterator_php7x(build_dir: Path) -> list[str]:
    """Behebt UBool/bool-Konflikt in ext/intl mit ICU >= 72.

    ICU änderte den Rückgabetyp von BreakIterator::operator== von UBool
    auf bool. PHP < 8.0 deklariert und implementiert noch UBool, was einen
    C++-Compilerfehler wegen konfligierendem Rückgabetyp auslöst.
    """
    intl_dir = build_dir / "ext" / "intl" / "breakiterator"
    patched = False

    header = intl_dir / "codepointiterator_internal.h"
    if header.exists():
        old = "virtual UBool operator==(const BreakIterator& that) const;"
        new = "virtual bool operator==(const BreakIterator& that) const;"
        content = header.read_text()
        if old in content:
            header.write_text(content.replace(old, new))
            patched = True

    impl = intl_dir / "codepointiterator_internal.cpp"
    if impl.exists():
        old = "UBool CodePointBreakIterator::operator==(const BreakIterator& that) const"
        new = "bool CodePointBreakIterator::operator==(const BreakIterator& that) const"
        content = impl.read_text()
        if old in content:
            impl.write_text(content.replace(old, new))
            patched = True

    return ["intl: UBool → bool für BreakIterator::operator== (ICU >= 72)"] if patched else []


def _patch_icu_true_false_php7x(build_dir: Path) -> list[str]:
    """Ersetzt TRUE/FALSE durch 1/0 in allen ext/intl-Quelldateien (ICU >= 68).

    ICU entfernte die TRUE/FALSE-Makros in Version 68 wegen Konflikten mit
    C99-stdbool.h. PHP < 8.0 verwendet diese Makros in ext/intl noch direkt.
    Betrifft alle .c/.cpp-Dateien im intl-Verzeichnis.
    """
    intl_dir = build_dir / "ext" / "intl"
    if not intl_dir.exists():
        return []

    patched = False
    for path in intl_dir.rglob("*"):
        if path.suffix not in (".c", ".cpp"):
            continue
        content = path.read_text()
        new_content = re.sub(r'\bTRUE\b', '1', content)
        new_content = re.sub(r'\bFALSE\b', '0', new_content)
        if new_content != content:
            path.write_text(new_content)
            patched = True
    return ["intl: TRUE/FALSE → 1/0 für ICU >= 68"] if patched else []


def _patch_icu_namespace_php7x(build_dir: Path) -> list[str]:
    """Ergänzt 'using namespace icu;' im zentralen intl-Shim-Header (ICU >= 60).

    ICU 60 setzte U_USING_ICU_NAMESPACE auf 0 – seitdem wird 'using namespace icu'
    nicht mehr automatisch gesetzt. PHP < 8.0 verwendet ICU-Typen wie UnicodeString
    ohne icu::-Prefix, was zu Compile-Fehlern führt. Der Shim-Header wird einmalig
    von allen betroffenen .cpp-Dateien eingebunden.
    """
    shim = build_dir / "ext" / "intl" / "intl_cppshims.h"
    if not shim.exists():
        return []

    injection = (
        "\n/* pbrew compat: ICU >= 60 setzt U_USING_ICU_NAMESPACE=0 */\n"
        "#include <unicode/uversion.h>\n"
        "#if !U_USING_ICU_NAMESPACE\n"
        "using namespace icu;\n"
        "#endif\n"
    )

    content = shim.read_text()
    if "U_USING_ICU_NAMESPACE" in content:
        return []

    shim.write_text(content.replace("#endif", f"#endif{injection}", 1))
    return ["intl: using namespace icu für ICU >= 60 (U_USING_ICU_NAMESPACE=0)"]


def _patch_icu_breakiterator_class_using(build_dir: Path) -> list[str]:
    """Ergänzt 'using icu::BreakIterator' in breakiterator_class.h (PHP 7.0/7.2).

    PHP 7.3+ hat diesen Fix bereits. Ohne ihn ist BreakIterator undefiniert wenn
    USE_BREAKITERATOR_POINTER gesetzt ist und der ICU-Namespace noch nicht sichtbar.
    """
    header = build_dir / "ext" / "intl" / "breakiterator" / "breakiterator_class.h"
    if not header.exists():
        return []

    old = "#ifndef USE_BREAKITERATOR_POINTER\ntypedef void BreakIterator;\n#endif"
    new = "#ifndef USE_BREAKITERATOR_POINTER\ntypedef void BreakIterator;\n#else\nusing icu::BreakIterator;\n#endif"

    content = header.read_text()
    if old not in content:
        return []

    header.write_text(content.replace(old, new))
    return ["intl: using icu::BreakIterator in breakiterator_class.h (PHP < 7.3)"]


def _patch_icu_convertcpp_h_using(build_dir: Path) -> list[str]:
    """Ergänzt 'using icu::UnicodeString' in intl_convertcpp.h (PHP < 7.3).

    PHP 7.3+ hat diesen Eintrag bereits. Ohne ihn ist UnicodeString in .cpp-Dateien
    undefiniert, die intl_convertcpp.h einbinden.
    """
    header = build_dir / "ext" / "intl" / "intl_convertcpp.h"
    if not header.exists():
        return []

    marker = "using icu::UnicodeString;"
    content = header.read_text()
    if marker in content:
        return []

    # Nach dem letzten #include einfügen
    last_include = content.rfind("#include")
    if last_include == -1:
        return []
    line_end = content.index("\n", last_include)
    content = content[:line_end + 1] + f"\n{marker}\n" + content[line_end + 1:]
    header.write_text(content)
    return ["intl: using icu::UnicodeString in intl_convertcpp.h (PHP < 7.3)"]


def _patch_icu_codepointiterator_h(build_dir: Path) -> list[str]:
    """Ergänzt 'using icu::...' in codepointiterator_internal.h (PHP < 7.3).

    PHP 7.3 ergänzte spezifische using-Deklarationen im Header selbst.
    Ohne sie matcht der Compiler Methoden-Signaturen wie getText/setText/adoptText
    nicht – 'no declaration matches' – und CodePointBreakIterator bleibt abstrakt.
    """
    header = build_dir / "ext" / "intl" / "breakiterator" / "codepointiterator_internal.h"
    if not header.exists():
        return []

    marker = "using icu::CharacterIterator;"
    content = header.read_text()
    if marker in content:
        return []

    injection = (
        "\nusing icu::BreakIterator;\n"
        "using icu::CharacterIterator;\n"
        "using icu::UnicodeString;\n"
    )

    last_include = content.rfind("#include")
    if last_include == -1:
        return []
    line_end = content.index("\n", last_include)
    content = content[:line_end + 1] + injection + content[line_end + 1:]
    header.write_text(content)
    return ["intl: using icu::{BreakIterator,CharacterIterator,UnicodeString} in codepointiterator_internal.h (PHP < 7.3)"]


def _patch_icu_cpp_using_all(build_dir: Path) -> list[str]:
    """Ergänzt 'using namespace icu' in allen ext/intl .cpp-Dateien (PHP < 7.3).

    PHP 7.3+ hat spezifische using-Deklarationen in betroffene Dateien eingefügt.
    Für PHP < 7.3 patchen wir alle .cpp-Dateien, die ICU-Header einbinden aber
    noch kein 'using namespace icu' haben – korrekte Praxis in .cpp-Dateien.
    """
    intl_dir = build_dir / "ext" / "intl"
    if not intl_dir.exists():
        return []

    marker = "using namespace icu;"
    count = 0
    for path in intl_dir.rglob("*.cpp"):
        content = path.read_text()
        if marker in content:
            continue
        last_icu = content.rfind("#include <unicode/")
        if last_icu == -1:
            continue
        line_end = content.index("\n", last_icu)
        path.write_text(content[:line_end + 1] + f"\n{marker}\n" + content[line_end + 1:])
        count += 1
    return [f"intl: using namespace icu in {count} .cpp-Dateien (PHP < 7.3)"] if count else []


def prepare_configure_env(build_dir: Path, php_version: str) -> "Path | None":
    """Erstellt Hilfsskripte die vor configure im PATH gebraucht werden.

    Gibt den Pfad zum tools-Verzeichnis zurück (in PATH einhängen) oder None.
    Wird direkt vor configure aufgerufen.
    """
    parts = php_version.split(".")
    major, minor = int(parts[0]), int(parts[1])

    if (major, minor) < (8, 0):
        return _create_icu_config_wrapper(build_dir)
    return None


def _create_icu_config_wrapper(build_dir: Path) -> "Path | None":
    """Erstellt einen pkg-config-basierten icu-config-Wrapper für PHP 7.x.

    PHP < 7.2 kennt kein pkg-config in PHP_SETUP_ICU und fällt auf icu-config
    zurück. Das System-icu-config ist auf modernen Ubuntu/Debian-Systemen kaputt
    (liefert pkgdata.inc statt korrekter Flags). Der Wrapper delegiert alle
    icu-config-Aufrufe an pkg-config.
    """
    import subprocess
    try:
        subprocess.check_output(
            ["pkg-config", "--exists", "icu-uc"],
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None

    tools_dir = build_dir / ".pbrew-tools"
    tools_dir.mkdir(exist_ok=True)
    wrapper = tools_dir / "icu-config"
    wrapper.write_text("""\
#!/bin/bash
case "$1" in
  --prefix)              pkg-config --variable=prefix icu-uc ;;
  --version)             pkg-config --modversion icu-uc ;;
  --ldflags-libsonly)    pkg-config --libs-only-l icu-uc icu-io icu-i18n ;;
  --ldflags)             pkg-config --libs icu-uc icu-io icu-i18n ;;
  --cppflags-searchpath) pkg-config --cflags-only-I icu-uc ;;
  --cppflags)            pkg-config --cflags icu-uc ;;
  --cxxflags)            pkg-config --variable=CXXFLAGS icu-uc 2>/dev/null ;;
  *)                     /usr/bin/icu-config "$@" ;;
esac
""")
    wrapper.chmod(0o755)
    return tools_dir


def apply_post_configure_patches(build_dir: Path, php_version: str) -> list[str]:
    """Wendet Patches auf das generierte Makefile an (nach configure, vor make)."""
    parts = php_version.split(".")
    major, minor = int(parts[0]), int(parts[1])
    applied: list[str] = []

    if (major, minor) < (8, 0):
        applied.extend(_patch_makefile_icu_extra_libs(build_dir))

    return applied


def _patch_makefile_icu_extra_libs(build_dir: Path) -> list[str]:
    """Ergänzt ICU-Libs in EXTRA_LIBS im generierten Makefile (PHP < 7.3, statisches intl).

    PHP 7.0-7.2 legt ICU-Libs nur in INTL_SHARED_LIBADD ab, das bei statisch
    kompiliertem intl nicht in den SAPI-Link-Befehlen landet. Das Makefile wird
    direkt korrigiert, weil configure schon gelaufen ist.
    """
    import shutil
    makefile = build_dir / "Makefile"
    if not makefile.exists():
        return []

    icu_libs = _icu_libs_from_pkgconfig()
    if not icu_libs:
        return []

    content = makefile.read_text()

    # Prüfen ob ICU-Libs schon in EXTRA_LIBS stehen
    extra_libs_match = re.search(r'^EXTRA_LIBS\s*=(.*)$', content, re.MULTILINE)
    if not extra_libs_match:
        return []

    current = extra_libs_match.group(1)
    if any(lib in current for lib in icu_libs):
        return []

    libs_str = " " + " ".join(icu_libs)
    new_line = f"EXTRA_LIBS ={current}{libs_str}"
    content = content[:extra_libs_match.start()] + new_line + content[extra_libs_match.end():]
    makefile.write_text(content)
    return [f"Makefile: ICU-Libs ({' '.join(icu_libs)}) zu EXTRA_LIBS ergänzt (PHP < 7.3)"]


def _icu_libs_from_pkgconfig() -> list[str]:
    """Fragt pkg-config nach den ICU-Link-Flags."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["pkg-config", "--libs", "icu-uc", "icu-io", "icu-i18n"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return out.split()
    except Exception:
        return []
