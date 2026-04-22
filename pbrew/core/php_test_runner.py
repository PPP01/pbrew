"""Fuehrt PHP-Integrationstests gegen ein installiertes PHP-Binary aus."""
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestCase:
    name: str
    category: str
    code: str
    min_version: tuple[int, ...] = (0, 0, 0)
    max_version: tuple[int, ...] = (999, 999, 999)


@dataclass
class TestResult:
    name: str
    category: str
    passed: bool
    skipped: bool = False
    skip_reason: str = ""
    error: str = ""


def run_tests(
    php_bin: Path,
    php_version: str,
    categories: list[str] | None = None,
) -> list[TestResult]:
    """Fuehrt alle (oder gefilterte) Tests gegen php_bin aus."""
    version_tuple = _parse_version(php_version)
    all_tests = _build_test_suite()
    selected = [t for t in all_tests if categories is None or t.category in categories]

    results: list[TestResult] = []
    for test in selected:
        if version_tuple < test.min_version:
            results.append(TestResult(
                test.name, test.category,
                passed=False, skipped=True,
                skip_reason=f"erfordert PHP {_fmt_version(test.min_version)}+",
            ))
            continue
        if version_tuple > test.max_version:
            results.append(TestResult(
                test.name, test.category,
                passed=False, skipped=True,
                skip_reason=f"nur bis PHP {_fmt_version(test.max_version)}",
            ))
            continue
        results.append(_run_one(php_bin, test))
    return results


def _run_one(php_bin: Path, test: TestCase) -> TestResult:
    with tempfile.NamedTemporaryFile(suffix=".php", mode="w", delete=False) as f:
        f.write("<?php\n" + test.code)
        fname = Path(f.name)
    try:
        proc = subprocess.run(
            [str(php_bin), str(fname)],
            capture_output=True, text=True, timeout=15,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        if stdout == "OK":
            return TestResult(test.name, test.category, passed=True)
        if stdout.startswith("SKIP:"):
            return TestResult(
                test.name, test.category,
                passed=False, skipped=True,
                skip_reason=stdout[5:].strip(),
            )
        error = stdout if stdout else stderr[:200]
        return TestResult(test.name, test.category, passed=False, error=error)
    except subprocess.TimeoutExpired:
        return TestResult(test.name, test.category, passed=False, error="Timeout (>15s)")
    finally:
        fname.unlink(missing_ok=True)


def _parse_version(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split(".")[:3])
    except ValueError:
        return (0, 0, 0)


def _fmt_version(t: tuple[int, ...]) -> str:
    return ".".join(str(x) for x in t)


# ── Test-Suite ────────────────────────────────────────────────────────────────

def _build_test_suite() -> list[TestCase]:
    tests: list[TestCase] = []

    # ── basic ─────────────────────────────────────────────────────────────────

    tests.append(TestCase("arithmetic", "basic", """
$ok = (2 + 3 * 4 === 14)
   && ((int)(7 / 2) === 3)
   && (abs(-42) === 42)
   && (round(2.555, 2) === 2.56);
echo $ok ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("strings", "basic", """
$ok = (strlen('pbrew') === 5)
   && (strtoupper('pbrew') === 'PBREW')
   && (substr('pbrew', 1, 3) === 'bre')
   && (str_replace('e', 'a', 'pbrew') === 'pbraw');
echo $ok ? 'OK' : 'FAIL';
"""))

    # PHP < 7.4 kennt keine Arrow Functions
    tests.append(TestCase("arrays", "basic", """
$a = array_map(fn($x) => $x * 2, [1, 2, 3]);
$b = array_filter([1, 2, 3, 4], fn($x) => $x % 2 === 0);
$ok = ($a === [2, 4, 6]) && (array_values($b) === [2, 4]);
echo $ok ? 'OK' : 'FAIL';
""", min_version=(7, 4, 0)))

    tests.append(TestCase("arrays (closures)", "basic", """
$a = array_map(function($x) { return $x * 2; }, [1, 2, 3]);
$b = array_filter([1, 2, 3, 4], function($x) { return $x % 2 === 0; });
$ok = ($a === [2, 4, 6]) && (array_values($b) === [2, 4]);
echo $ok ? 'OK' : 'FAIL';
""", max_version=(7, 3, 99)))

    tests.append(TestCase("exceptions", "basic", """
try {
    throw new RuntimeException('test', 42);
} catch (RuntimeException $e) {
    echo ($e->getMessage() === 'test' && $e->getCode() === 42) ? 'OK' : 'FAIL';
}
"""))

    tests.append(TestCase("json", "basic", """
$data = ['name' => 'pbrew', 'version' => 1, 'ok' => true];
$json = json_encode($data);
$back = json_decode($json, true);
echo ($back === $data) ? 'OK' : 'FAIL';
"""))

    # ── ssl ───────────────────────────────────────────────────────────────────

    tests.append(TestCase("extension geladen", "ssl", """
echo extension_loaded('openssl') ? 'OK' : 'FAIL: openssl nicht geladen';
"""))

    tests.append(TestCase("RSA key generation", "ssl", """
$kp = openssl_pkey_new(['private_key_bits' => 1024, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
echo ($kp !== false) ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("RSA sign/verify", "ssl", """
$kp = openssl_pkey_new(['private_key_bits' => 1024, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
$data = 'pbrew-test-data';
if (!openssl_sign($data, $sig, $kp)) { echo 'FAIL:sign'; exit; }
$pub = openssl_pkey_get_details($kp);
echo openssl_verify($data, $sig, $pub['key']) === 1 ? 'OK' : 'FAIL:verify';
"""))

    tests.append(TestCase("RSA key details", "ssl", """
$kp = openssl_pkey_new(['private_key_bits' => 1024, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
$d = openssl_pkey_get_details($kp);
$ok = isset($d['rsa']['n'], $d['rsa']['e'], $d['rsa']['d'], $d['bits'])
   && $d['bits'] === 1024;
echo $ok ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("AES-256-CBC encrypt/decrypt", "ssl", """
$key = openssl_random_pseudo_bytes(32);
$iv  = openssl_random_pseudo_bytes(16);
$plain = 'pbrew-test-plaintext';
$enc = openssl_encrypt($plain, 'AES-256-CBC', $key, OPENSSL_RAW_DATA, $iv);
$dec = openssl_decrypt($enc, 'AES-256-CBC', $key, OPENSSL_RAW_DATA, $iv);
echo ($dec === $plain) ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("X.509 Zertifikat", "ssl", """
// Minimale openssl.cnf – umgeht system-weite TSA/CA-Konfigurationen
$cfg = tempnam(sys_get_temp_dir(), 'pbrew') . '.cnf';
file_put_contents($cfg, "[req]\ndistinguished_name=req_dn\n[req_dn]\n");
$dn = ['CN' => 'pbrew-test', 'O' => 'Test', 'C' => 'DE'];
$kp = openssl_pkey_new(['private_key_bits' => 1024, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
$csr  = openssl_csr_new($dn, $kp, ['config' => $cfg]);
$cert = $csr ? openssl_csr_sign($csr, null, $kp, 1, ['config' => $cfg]) : false;
unlink($cfg);
echo ($cert !== false) ? 'OK' : 'FAIL';
"""))

    # ── hash ──────────────────────────────────────────────────────────────────

    tests.append(TestCase("sha256", "hash", """
$h = hash('sha256', 'pbrew');
echo strlen($h) === 64 && ctype_xdigit($h) ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("sha3-256", "hash", """
$h = hash('sha3-256', 'pbrew');
echo strlen($h) === 64 && ctype_xdigit($h) ? 'OK' : 'FAIL';
""", min_version=(7, 1, 0)))

    tests.append(TestCase("hmac-sha256", "hash", """
$h1 = hash_hmac('sha256', 'data', 'key');
$h2 = hash_hmac('sha256', 'data', 'key');
$h3 = hash_hmac('sha256', 'data', 'other');
echo ($h1 === $h2 && $h1 !== $h3) ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("bcrypt", "hash", """
$hash = password_hash('pbrew', PASSWORD_BCRYPT);
echo password_verify('pbrew', $hash) && !password_verify('wrong', $hash) ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("argon2i", "hash", """
if (!defined('PASSWORD_ARGON2I') || !in_array('argon2i', password_algos())) {
    echo 'SKIP: argon2i nicht kompiliert'; exit;
}
$hash = password_hash('pbrew', PASSWORD_ARGON2I);
echo password_verify('pbrew', $hash) && !password_verify('wrong', $hash) ? 'OK' : 'FAIL';
""", min_version=(7, 2, 0)))

    tests.append(TestCase("argon2id", "hash", """
if (!defined('PASSWORD_ARGON2ID') || !in_array('argon2id', password_algos())) {
    echo 'SKIP: argon2id nicht kompiliert'; exit;
}
$hash = password_hash('pbrew', PASSWORD_ARGON2ID);
echo password_verify('pbrew', $hash) && !password_verify('wrong', $hash) ? 'OK' : 'FAIL';
""", min_version=(7, 3, 0)))

    tests.append(TestCase("random_bytes", "hash", """
$a = random_bytes(32);
$b = random_bytes(32);
echo (strlen($a) === 32 && $a !== $b) ? 'OK' : 'FAIL';
""", min_version=(7, 0, 0)))

    # ── modules ───────────────────────────────────────────────────────────────

    tests.append(TestCase("mbstring", "modules", """
if (!extension_loaded('mbstring')) { echo 'SKIP: mbstring fehlt'; exit; }
$ok = mb_strlen('Aerger') === 6
   && mb_strtoupper('pbrew') === 'PBREW'
   && mb_substr('pbrew', 1, 3) === 'bre';
echo $ok ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("mbstring unicode", "modules", """
if (!extension_loaded('mbstring')) { echo 'SKIP: mbstring fehlt'; exit; }
$s = "Stra\xc3\x9fe";
echo mb_strlen($s) === 6 && mb_strtoupper($s) === "STRASSE" ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("pdo_sqlite", "modules", """
if (!extension_loaded('pdo_sqlite')) { echo 'SKIP: pdo_sqlite fehlt'; exit; }
try {
    $db = new PDO('sqlite::memory:');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec('CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)');
    $db->prepare('INSERT INTO t (v) VALUES (?)')->execute(['pbrew']);
    $row = $db->query('SELECT v FROM t')->fetch(PDO::FETCH_ASSOC);
    echo $row['v'] === 'pbrew' ? 'OK' : 'FAIL';
} catch (Exception $e) {
    echo 'FAIL: ' . $e->getMessage();
}
"""))

    tests.append(TestCase("pcre", "modules", """
$ok = preg_match('/^pbrew-(\\d+)$/', 'pbrew-42', $m) === 1
   && $m[1] === '42'
   && preg_replace('/[aeiou]/', '*', 'pbrew') === 'pbr*w';
echo $ok ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("ctype", "modules", """
if (!extension_loaded('ctype')) { echo 'SKIP: ctype fehlt'; exit; }
$ok = ctype_alpha('pbrew')
   && ctype_digit('42')
   && !ctype_digit('abc');
echo $ok ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("intl", "modules", """
if (!extension_loaded('intl')) { echo 'SKIP: intl fehlt'; exit; }
$ok = class_exists('Collator') && class_exists('NumberFormatter');
echo $ok ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("date/timezone", "modules", """
$tz = new DateTimeZone('Europe/Berlin');
$dt = new DateTime('2024-01-15 12:00:00', $tz);
$ok = $dt->format('Y') === '2024' && $tz->getName() === 'Europe/Berlin';
echo $ok ? 'OK' : 'FAIL';
"""))

    tests.append(TestCase("curl", "modules", """
if (!extension_loaded('curl')) { echo 'SKIP: curl fehlt'; exit; }
$ver = curl_version();
echo isset($ver['version']) ? 'OK' : 'FAIL';
"""))

    return tests


CATEGORIES = ["basic", "ssl", "hash", "modules"]
