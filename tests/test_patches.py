from pathlib import Path
import pytest
from unittest.mock import patch as mock_patch
from pbrew.core.patches import apply_compat_patches, apply_post_configure_patches


OPENSSL_C_WITH_BUG = '''\
\tREGISTER_LONG_CONSTANT("OPENSSL_PKCS1_PADDING", RSA_PKCS1_PADDING, CONST_CS|CONST_PERSISTENT);
\tREGISTER_LONG_CONSTANT("OPENSSL_SSLV23_PADDING", RSA_SSLV23_PADDING, CONST_CS|CONST_PERSISTENT);
\tREGISTER_LONG_CONSTANT("OPENSSL_NO_PADDING", RSA_NO_PADDING, CONST_CS|CONST_PERSISTENT);
'''

OPENSSL_C_PATCHED = '''\
\tREGISTER_LONG_CONSTANT("OPENSSL_PKCS1_PADDING", RSA_PKCS1_PADDING, CONST_CS|CONST_PERSISTENT);
#ifdef RSA_SSLV23_PADDING
\tREGISTER_LONG_CONSTANT("OPENSSL_SSLV23_PADDING", RSA_SSLV23_PADDING, CONST_CS|CONST_PERSISTENT);
#endif
\tREGISTER_LONG_CONSTANT("OPENSSL_NO_PADDING", RSA_NO_PADDING, CONST_CS|CONST_PERSISTENT);
'''


def _make_openssl_c(tmp_path: Path, content: str) -> Path:
    ext_dir = tmp_path / "ext" / "openssl"
    ext_dir.mkdir(parents=True)
    f = ext_dir / "openssl.c"
    f.write_text(content)
    return f


def test_patch_applied_for_php74(tmp_path):
    f = _make_openssl_c(tmp_path, OPENSSL_C_WITH_BUG)
    patches = apply_compat_patches(tmp_path, "7.4.33")
    assert len(patches) == 1
    assert "RSA_SSLV23_PADDING" in patches[0]
    assert f.read_text() == OPENSSL_C_PATCHED


def test_patch_applied_for_php56(tmp_path):
    _make_openssl_c(tmp_path, OPENSSL_C_WITH_BUG)
    patches = apply_compat_patches(tmp_path, "5.6.40")
    assert len(patches) == 1


def test_no_patch_for_php80(tmp_path):
    _make_openssl_c(tmp_path, OPENSSL_C_WITH_BUG)
    patches = apply_compat_patches(tmp_path, "8.0.30")
    assert patches == []


def test_no_patch_for_php84(tmp_path):
    _make_openssl_c(tmp_path, OPENSSL_C_WITH_BUG)
    patches = apply_compat_patches(tmp_path, "8.4.22")
    assert patches == []


def test_patch_idempotent(tmp_path):
    f = _make_openssl_c(tmp_path, OPENSSL_C_WITH_BUG)
    apply_compat_patches(tmp_path, "7.4.33")
    patches = apply_compat_patches(tmp_path, "7.4.33")
    assert patches == []
    assert f.read_text() == OPENSSL_C_PATCHED


def test_no_openssl_c_returns_empty(tmp_path):
    patches = apply_compat_patches(tmp_path, "7.4.33")
    assert patches == []


# ── ICU TRUE/FALSE patch ──────────────────────────────────────────────────────

def _make_collator_sort(tmp_path: Path, content: str) -> Path:
    d = tmp_path / "ext" / "intl" / "collator"
    d.mkdir(parents=True)
    f = d / "collator_sort.c"
    f.write_text(content)
    return f


def test_icu_true_false_patch_collator(tmp_path):
    src = "collator_sort_internal( TRUE, X );\ncollator_sort_internal( FALSE, X );"
    f = _make_collator_sort(tmp_path, src)
    patches = apply_compat_patches(tmp_path, "7.2.34")
    assert any("TRUE/FALSE" in p for p in patches)
    assert "TRUE" not in f.read_text()
    assert "FALSE" not in f.read_text()
    assert "collator_sort_internal( 1, X );" in f.read_text()


def test_icu_true_false_no_patch_for_php80(tmp_path):
    _make_collator_sort(tmp_path, "collator_sort_internal( TRUE, X );")
    patches = apply_compat_patches(tmp_path, "8.0.30")
    assert not any("TRUE/FALSE" in p for p in patches)


def test_icu_true_false_idempotent(tmp_path):
    src = "collator_sort_internal( TRUE, X );"
    f = _make_collator_sort(tmp_path, src)
    apply_compat_patches(tmp_path, "7.2.34")
    patches = apply_compat_patches(tmp_path, "7.2.34")
    assert not any("TRUE/FALSE" in p for p in patches)
    assert f.read_text() == "collator_sort_internal( 1, X );"


# ── ICU namespace patch ───────────────────────────────────────────────────────

SHIM_ORIGINAL = "#ifndef INTL_CPPSHIMS_H\n#define INTL_CPPSHIMS_H\n// body\n#endif\n"


def _make_shim(tmp_path: Path, content: str) -> Path:
    d = tmp_path / "ext" / "intl"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "intl_cppshims.h"
    f.write_text(content)
    return f


def test_icu_namespace_patch_applied(tmp_path):
    f = _make_shim(tmp_path, SHIM_ORIGINAL)
    patches = apply_compat_patches(tmp_path, "7.0.33")
    assert any("U_USING_ICU_NAMESPACE" in p for p in patches)
    assert "using namespace icu" in f.read_text()


def test_icu_namespace_no_patch_for_php80(tmp_path):
    _make_shim(tmp_path, SHIM_ORIGINAL)
    patches = apply_compat_patches(tmp_path, "8.0.30")
    assert not any("U_USING_ICU_NAMESPACE" in p for p in patches)


def test_icu_namespace_idempotent(tmp_path):
    f = _make_shim(tmp_path, SHIM_ORIGINAL)
    apply_compat_patches(tmp_path, "7.0.33")
    patches = apply_compat_patches(tmp_path, "7.0.33")
    assert not any("U_USING_ICU_NAMESPACE" in p for p in patches)
    assert f.read_text().count("using namespace icu") == 1


# ── breakiterator_class.h using-patch ────────────────────────────────────────

BRKCLASS_OLD = "#ifndef USE_BREAKITERATOR_POINTER\ntypedef void BreakIterator;\n#endif"
BRKCLASS_NEW = "#ifndef USE_BREAKITERATOR_POINTER\ntypedef void BreakIterator;\n#else\nusing icu::BreakIterator;\n#endif"


def _make_brkclass_h(tmp_path: Path, content: str) -> Path:
    d = tmp_path / "ext" / "intl" / "breakiterator"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "breakiterator_class.h"
    f.write_text(content)
    return f


def test_brkclass_using_patch_for_php70(tmp_path):
    f = _make_brkclass_h(tmp_path, BRKCLASS_OLD)
    patches = apply_compat_patches(tmp_path, "7.0.33")
    assert any("icu::BreakIterator" in p for p in patches)
    assert f.read_text() == BRKCLASS_NEW


def test_brkclass_using_patch_for_php72(tmp_path):
    f = _make_brkclass_h(tmp_path, BRKCLASS_OLD)
    patches = apply_compat_patches(tmp_path, "7.2.34")
    assert any("icu::BreakIterator" in p for p in patches)
    assert f.read_text() == BRKCLASS_NEW


def test_brkclass_using_no_patch_when_already_fixed(tmp_path):
    _make_brkclass_h(tmp_path, BRKCLASS_NEW)
    patches = apply_compat_patches(tmp_path, "7.0.33")
    assert not any("icu::BreakIterator" in p for p in patches)


def test_brkclass_using_no_patch_for_php80(tmp_path):
    _make_brkclass_h(tmp_path, BRKCLASS_OLD)
    patches = apply_compat_patches(tmp_path, "8.0.30")
    assert not any("icu::BreakIterator" in p for p in patches)


# ── ICU BreakIterator patch ───────────────────────────────────────────────────

BREAKITER_H_BUG  = "virtual UBool operator==(const BreakIterator& that) const;"
BREAKITER_H_FIXED = "virtual bool operator==(const BreakIterator& that) const;"
BREAKITER_CPP_BUG  = "UBool CodePointBreakIterator::operator==(const BreakIterator& that) const"
BREAKITER_CPP_FIXED = "bool CodePointBreakIterator::operator==(const BreakIterator& that) const"


def _make_breakiter_files(tmp_path: Path) -> tuple[Path, Path]:
    d = tmp_path / "ext" / "intl" / "breakiterator"
    d.mkdir(parents=True)
    h = d / "codepointiterator_internal.h"
    cpp = d / "codepointiterator_internal.cpp"
    h.write_text(BREAKITER_H_BUG)
    cpp.write_text(BREAKITER_CPP_BUG)
    return h, cpp


def test_icu_patch_applied_for_php73(tmp_path):
    h, cpp = _make_breakiter_files(tmp_path)
    patches = apply_compat_patches(tmp_path, "7.3.33")
    assert any("UBool" in p for p in patches)
    assert h.read_text() == BREAKITER_H_FIXED
    assert cpp.read_text() == BREAKITER_CPP_FIXED


def test_icu_patch_applied_for_php74(tmp_path):
    h, cpp = _make_breakiter_files(tmp_path)
    patches = apply_compat_patches(tmp_path, "7.4.33")
    assert any("UBool" in p for p in patches)
    assert h.read_text() == BREAKITER_H_FIXED
    assert cpp.read_text() == BREAKITER_CPP_FIXED


def test_icu_no_patch_for_php80(tmp_path):
    _make_breakiter_files(tmp_path)
    patches = apply_compat_patches(tmp_path, "8.0.30")
    assert not any("UBool" in p for p in patches)


def test_icu_patch_idempotent(tmp_path):
    h, cpp = _make_breakiter_files(tmp_path)
    apply_compat_patches(tmp_path, "7.4.33")
    patches = apply_compat_patches(tmp_path, "7.4.33")
    assert not any("UBool" in p for p in patches)
    assert h.read_text() == BREAKITER_H_FIXED
    assert cpp.read_text() == BREAKITER_CPP_FIXED


# ── codepointiterator_internal.h using-patch ─────────────────────────────────

CPBRKITER_H_BUG = (
    "#include <unicode/brkiter.h>\n"
    "#include <unicode/unistr.h>\n"
    "\nnamespace PHP {\n"
    "\tclass CodePointBreakIterator : public BreakIterator {};\n"
    "}\n"
)


def _make_codepointiterator_h(tmp_path: Path, content: str) -> Path:
    d = tmp_path / "ext" / "intl" / "breakiterator"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "codepointiterator_internal.h"
    f.write_text(content)
    return f


def test_codepointiterator_h_using_patch_applied(tmp_path):
    f = _make_codepointiterator_h(tmp_path, CPBRKITER_H_BUG)
    patches = apply_compat_patches(tmp_path, "7.0.33")
    assert any("CharacterIterator" in p for p in patches)
    content = f.read_text()
    assert "using icu::BreakIterator;" in content
    assert "using icu::CharacterIterator;" in content
    assert "using icu::UnicodeString;" in content


def test_codepointiterator_h_no_patch_for_php80(tmp_path):
    _make_codepointiterator_h(tmp_path, CPBRKITER_H_BUG)
    patches = apply_compat_patches(tmp_path, "8.0.30")
    assert not any("CharacterIterator" in p for p in patches)


def test_codepointiterator_h_idempotent(tmp_path):
    f = _make_codepointiterator_h(tmp_path, CPBRKITER_H_BUG)
    apply_compat_patches(tmp_path, "7.0.33")
    patches = apply_compat_patches(tmp_path, "7.0.33")
    assert not any("CharacterIterator" in p for p in patches)
    assert f.read_text().count("using icu::CharacterIterator;") == 1


# ── Post-configure Makefile ICU-Libs patch ───────────────────────────────────

_MAKEFILE_WITHOUT_ICU = """\
CC = gcc
EXTRA_LIBS = -lresolv -lcrypt -lm
LDFLAGS = -L/usr/lib
"""

_ICU_LIBS = ["-licuio", "-licui18n", "-licuuc", "-licudata"]


def _make_makefile(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "Makefile"
    f.write_text(content)
    return f


def test_post_configure_icu_libs_added(tmp_path):
    f = _make_makefile(tmp_path, _MAKEFILE_WITHOUT_ICU)
    with mock_patch("pbrew.core.patches._icu_libs_from_pkgconfig", return_value=_ICU_LIBS):
        patches = apply_post_configure_patches(tmp_path, "7.0.33")
    assert any("EXTRA_LIBS" in p for p in patches)
    content = f.read_text()
    assert "EXTRA_LIBS = -lresolv -lcrypt -lm -licuio" in content


def test_post_configure_icu_libs_no_patch_for_php80(tmp_path):
    _make_makefile(tmp_path, _MAKEFILE_WITHOUT_ICU)
    with mock_patch("pbrew.core.patches._icu_libs_from_pkgconfig", return_value=_ICU_LIBS):
        patches = apply_post_configure_patches(tmp_path, "8.0.30")
    assert patches == []


def test_post_configure_icu_libs_idempotent(tmp_path):
    f = _make_makefile(tmp_path, _MAKEFILE_WITHOUT_ICU)
    with mock_patch("pbrew.core.patches._icu_libs_from_pkgconfig", return_value=_ICU_LIBS):
        apply_post_configure_patches(tmp_path, "7.0.33")
        patches = apply_post_configure_patches(tmp_path, "7.0.33")
    assert patches == []
    assert f.read_text().count("-licuuc") == 1


def test_post_configure_no_makefile_returns_empty(tmp_path):
    with mock_patch("pbrew.core.patches._icu_libs_from_pkgconfig", return_value=_ICU_LIBS):
        patches = apply_post_configure_patches(tmp_path, "7.0.33")
    assert patches == []


# ── PHP 5.6 OpenSSL 3.x patches ──────────────────────────────────────────────

from pbrew.core.patches import _patch_openssl3_php56


def _make_openssl56_c(tmp_path: Path, extra: str = "") -> Path:
    d = tmp_path / "ext" / "openssl"
    d.mkdir(parents=True)
    f = d / "openssl.c"
    f.write_text("/* Common */\n#include <time.h>\n" + extra)
    return f


def _make_xp_ssl_c(tmp_path: Path) -> Path:
    d = tmp_path / "ext" / "openssl"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "xp_ssl.c"
    f.write_text(
        "\tif (method_value == STREAM_CRYPTO_METHOD_SSLv2) {\n"
        "#ifndef OPENSSL_NO_SSL2\n"
        "\t\treturn is_client ? SSLv2_client_method() : SSLv2_server_method();\n"
        "#else\n"
        '\t\tphp_error_docref(NULL TSRMLS_CC, E_WARNING, "no SSLv2");\n'
        "\t\treturn NULL;\n"
        "#endif\n"
        "\t}\n"
    )
    return f


def _make_phar_util_c(tmp_path: Path) -> Path:
    d = tmp_path / "ext" / "phar"
    d.mkdir(parents=True)
    f = d / "util.c"
    f.write_text(
        "\t\t\tEVP_MD_CTX md_ctx;\n"
        "\t\t\tEVP_VerifyInit(&md_ctx, mdtype);\n"
        "\t\t\tEVP_VerifyUpdate (&md_ctx, buf, len);\n"
        "\t\t\tEVP_VerifyFinal(&md_ctx, sig, sig_len, key);\n"
        "\t\t\tEVP_MD_CTX_cleanup(&md_ctx);\n"
    )
    return f


def test_evp_dss1_patch_for_php56(tmp_path):
    f = _make_openssl56_c(
        tmp_path,
        "\t\tcase OPENSSL_ALGO_DSS1:\n"
        "\t\t\tmdtype = (EVP_MD *) EVP_dss1();\n"
        "\t\t\tbreak;\n",
    )
    patches = _patch_openssl3_php56(tmp_path)
    assert any("EVP_dss1" in p for p in patches)
    assert "EVP_sha1()" in f.read_text()
    assert "EVP_dss1" not in f.read_text()


def test_sslv2_guard_patch_for_php56(tmp_path):
    _make_openssl56_c(tmp_path)
    f = _make_xp_ssl_c(tmp_path)
    _patch_openssl3_php56(tmp_path)
    content = f.read_text()
    assert "OPENSSL_VERSION_NUMBER < 0x10100000L" in content
    assert "#ifndef OPENSSL_NO_SSL2\n" not in content


def test_phar_evp_md_ctx_patch_for_php56(tmp_path):
    _make_openssl56_c(tmp_path)
    f = _make_phar_util_c(tmp_path)
    patches = _patch_openssl3_php56(tmp_path)
    assert any("phar" in p for p in patches)
    content = f.read_text()
    assert "EVP_MD_CTX *md_ctx = EVP_MD_CTX_new()" in content
    assert "EVP_MD_CTX md_ctx;" not in content
    assert "EVP_MD_CTX_cleanup" not in content
    assert "EVP_MD_CTX_free(md_ctx)" in content


def test_phar_patch_idempotent(tmp_path):
    _make_openssl56_c(tmp_path)
    _make_phar_util_c(tmp_path)
    _patch_openssl3_php56(tmp_path)
    patches = _patch_openssl3_php56(tmp_path)
    assert not any("phar" in p for p in patches)


def test_new_patches_no_effect_for_php80(tmp_path):
    _make_openssl56_c(
        tmp_path,
        "\t\tcase OPENSSL_ALGO_DSS1:\n\t\t\tmdtype = (EVP_MD *) EVP_dss1();\n\t\t\tbreak;\n",
    )
    _make_xp_ssl_c(tmp_path)
    _make_phar_util_c(tmp_path)
    from pbrew.core.patches import apply_compat_patches
    patches = apply_compat_patches(tmp_path, "8.0.30")
    assert not any("EVP_dss1" in p for p in patches)
    assert not any("SSLv2" in p for p in patches)
    assert not any("phar" in p for p in patches)


# ── EVP_CIPHER_CTX Stack→Heap (Step 16) ──────────────────────────────────────

def test_evp_cipher_ctx_stack_to_heap_for_php56(tmp_path):
    f = _make_openssl56_c(
        tmp_path,
        "\tEVP_CIPHER_CTX ctx;\n"
        "\tEVP_EncryptInit(&ctx, cipher, key, iv);\n"
        "\tEVP_SealUpdate(&ctx, out, &outl, in, inl);\n"
        "\tEVP_CIPHER_CTX_cleanup(&ctx);\n",
    )
    patches = _patch_openssl3_php56(tmp_path)
    assert any("EVP_CIPHER_CTX" in p for p in patches)
    content = f.read_text()
    assert "EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new()" in content
    assert "EVP_CIPHER_CTX ctx;" not in content
    assert "EVP_CIPHER_CTX_cleanup" not in content
    assert "EVP_CIPHER_CTX_reset(ctx)" in content
    assert "EVP_EncryptInit(ctx," in content
    assert "EVP_SealUpdate(ctx," in content


def test_evp_cipher_ctx_named_cipher_ctx_for_php56(tmp_path):
    f = _make_openssl56_c(
        tmp_path,
        "\tEVP_CIPHER_CTX cipher_ctx;\n"
        "\tEVP_EncryptInit_ex(&cipher_ctx, cipher, NULL, key, iv);\n"
        "\tEVP_DecryptUpdate(&cipher_ctx, out, &outl, in, inl);\n"
        "\tEVP_CIPHER_CTX_cleanup(&cipher_ctx);\n",
    )
    _patch_openssl3_php56(tmp_path)
    content = f.read_text()
    assert "EVP_CIPHER_CTX *cipher_ctx = EVP_CIPHER_CTX_new()" in content
    assert "EVP_EncryptInit_ex(cipher_ctx," in content
    assert "EVP_DecryptUpdate(cipher_ctx," in content
    assert "EVP_CIPHER_CTX_reset(cipher_ctx)" in content


# ── pkey->pkey.* global replacement (Step 14) ────────────────────────────────

def test_pkey_field_access_patch_for_php56(tmp_path):
    f = _make_openssl56_c(
        tmp_path,
        "\tif (pkey->pkey.rsa) rsa_func(pkey->pkey.rsa);\n"
        "\tif (pkey->pkey.dsa) dsa_func(pkey->pkey.dsa);\n"
        "\tif (pkey->pkey.dh)  dh_func(pkey->pkey.dh);\n"
        "\tif (pkey->pkey.ec)  ec_func(pkey->pkey.ec);\n",
    )
    _patch_openssl3_php56(tmp_path)
    content = f.read_text()
    assert "pkey->pkey.rsa" not in content
    assert "pkey->pkey.dsa" not in content
    assert "pkey->pkey.dh" not in content
    assert "pkey->pkey.ec" not in content
    assert "EVP_PKEY_get0_RSA(pkey)" in content
    assert "EVP_PKEY_get0_DSA(pkey)" in content
    assert "EVP_PKEY_get0_DH(pkey)" in content
    assert "EVP_PKEY_get0_EC_KEY(pkey)" in content


# ── pbrew_bn_to_zval Helper-Injektion (Step 1) ───────────────────────────────

def test_bn_to_zval_helper_injected_for_php56(tmp_path):
    f = _make_openssl56_c(tmp_path)
    _patch_openssl3_php56(tmp_path)
    content = f.read_text()
    assert "static void pbrew_bn_to_zval" in content
    assert "OPENSSL_VERSION_NUMBER >= 0x10100000L" in content
    assert "BN_bn2bin" in content
    assert "add_assoc_stringl" in content


def test_bn_to_zval_helper_injected_once(tmp_path):
    f = _make_openssl56_c(tmp_path)
    _patch_openssl3_php56(tmp_path)
    _patch_openssl3_php56(tmp_path)  # trifft Idempotenz-Guard
    assert f.read_text().count("static void pbrew_bn_to_zval") == 1


# ── pkey->type / EVP_PKEY_type(x->type) → EVP_PKEY_base_id (Step 3) ─────────

def test_pkey_type_patch_for_php56(tmp_path):
    f = _make_openssl56_c(
        tmp_path,
        "\tswitch (pkey->type) {\n"
        "\t\tcase EVP_PKEY_RSA: break;\n"
        "\t}\n"
        "\tif (EVP_PKEY_type(pkey->type) == EVP_PKEY_RSA) {}\n"
        "\tif (EVP_PKEY_type(key->type) == EVP_PKEY_DSA) {}\n",
    )
    _patch_openssl3_php56(tmp_path)
    content = f.read_text()
    assert "pkey->type" not in content
    assert "key->type" not in content
    assert "switch (EVP_PKEY_base_id(pkey))" in content
    assert "EVP_PKEY_base_id(pkey)" in content
    assert "EVP_PKEY_base_id(key)" in content


# ── openssl_pkey_get_details RSA-Block (Step 11) ─────────────────────────────

_PKEY_GET_DETAILS_RSA_OLD = (
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
    "\t\t\t}"
)


def test_pkey_get_details_rsa_patch_for_php56(tmp_path):
    f = _make_openssl56_c(tmp_path, _PKEY_GET_DETAILS_RSA_OLD)
    _patch_openssl3_php56(tmp_path)
    content = f.read_text()
    assert "pkey->pkey.rsa" not in content
    assert "OPENSSL_PKEY_GET_BN" not in content
    assert "EVP_PKEY_get0_RSA(pkey)" in content
    assert "RSA_get0_key(" in content
    assert "RSA_get0_factors(" in content
    assert "RSA_get0_crt_params(" in content
    assert 'pbrew_bn_to_zval(rsa, "n"' in content
    assert 'pbrew_bn_to_zval(rsa, "iqmp"' in content
    assert 'add_assoc_zval(return_value, "rsa", rsa)' in content


# ── EVP_MD_CTX Sign-Aufrufe ohne Leerzeichen (Regression für #spacing-bug) ───

def test_evp_md_ctx_sign_without_spaces_patch_for_php56(tmp_path):
    # PHP 5.6 hat EVP_SignInit(&md_ctx, ohne Leerzeichen vor (
    # Der alte Patch suchte nach "EVP_SignInit   (&md_ctx," (3 Spaces) → stiller No-op
    f = _make_openssl56_c(
        tmp_path,
        "\tEVP_MD_CTX md_ctx;\n"
        "\tEVP_SignInit(&md_ctx, mdtype);\n"
        "\tEVP_SignUpdate(&md_ctx, data, data_len);\n"
        "\tif (EVP_SignFinal(&md_ctx, sigbuf, &siglen, pkey)) {}\n"
        "\tEVP_MD_CTX_cleanup(&md_ctx);\n",
    )
    patches = _patch_openssl3_php56(tmp_path)
    assert any("EVP_MD_CTX" in p for p in patches)
    content = f.read_text()
    assert "EVP_MD_CTX *md_ctx = EVP_MD_CTX_new()" in content
    assert "&md_ctx" not in content
    assert "EVP_SignInit(md_ctx," in content
    assert "EVP_SignUpdate(md_ctx," in content
    assert "EVP_SignFinal(md_ctx," in content
    assert "EVP_MD_CTX_free(md_ctx)" in content
