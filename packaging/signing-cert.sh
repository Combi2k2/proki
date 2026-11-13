#!/usr/bin/env bash
# The certificate proki's macOS app is signed with, made once, so macOS keeps the permissions it was given
# from one build to the next. Free (self-signed): Gatekeeper still asks once, on the first open.
#
#     packaging/signing-cert.sh <folder to keep it in>
#
# Makes "Proki Signing" (good for 20 years: a new one would make every Mac ask again), puts it in your
# login keychain, trusted for signing code, for your own builds, and prints the three secrets to give
# GitHub. Keep the folder's proki-signing.p12 and its password safe and out of the repository.
set -euo pipefail

kept=${1:?the folder to keep the certificate in}
name="Proki Signing"
mkdir -p "$kept"
[ -e "$kept/proki-signing.p12" ] && { echo "$kept/proki-signing.p12 is there already: one certificate, kept for good" >&2; exit 1; }

room=$(mktemp -d)
trap 'rm -rf "$room"' EXIT
password=$(openssl rand -base64 24)

openssl req -x509 -newkey rsa:2048 -nodes -days 7300 -subj "/CN=$name" \
  -addext "keyUsage=critical,digitalSignature" -addext "extendedKeyUsage=critical,codeSigning" \
  -addext "basicConstraints=critical,CA:false" -keyout "$room/key.pem" -out "$room/cert.pem" 2>/dev/null
openssl pkcs12 -export -inkey "$room/key.pem" -in "$room/cert.pem" -name "$name" \
  -passout "pass:$password" -out "$kept/proki-signing.p12"   # macOS' own openssl: a .p12 its keychain reads
printf '%s\n' "$password" > "$kept/proki-signing.password"
chmod 600 "$kept/proki-signing.p12" "$kept/proki-signing.password"

security import "$kept/proki-signing.p12" -P "$password" -T /usr/bin/codesign -k "$HOME/Library/Keychains/login.keychain-db"
# codesign takes a certificate only once it's trusted for signing code: macOS asks for your password here
security add-trusted-cert -r trustRoot -p codeSign -k "$HOME/Library/Keychains/login.keychain-db" "$room/cert.pem"

cat <<EOF

Made "$name", in $kept and in your login keychain.

For the releases, in the repository's Settings > Secrets and variables > Actions, add:
  APPLE_CERTIFICATE           base64 -i "$kept/proki-signing.p12" | pbcopy   (then paste)
  APPLE_CERTIFICATE_PASSWORD  the line in $kept/proki-signing.password
  APPLE_SIGNING_IDENTITY      $name

For your own builds (npm run app), add to ~/.zshrc:
  export APPLE_SIGNING_IDENTITY="$name"
EOF
