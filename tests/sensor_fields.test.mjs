// Mirrors isSensitiveField() in src/quishguard/sensor.js (Stage 12b, check 1).
// Keep in sync with that function. Run: node tests/sensor_fields.test.mjs
function isSensitiveField(el) {
  if (el.type === "password") return true;
  if (el.autocomplete === "one-time-code") return true;
  if (el.autocomplete === "cc-number" || el.autocomplete === "cc-csc") return true;
  const hay = `${el.name || ""} ${el.placeholder || ""} ${el.id || ""} ${el.ariaLabel || ""}`.toLowerCase();
  if (/\b(otp|one[\s-]?time|2fa)\b/.test(hay)) return true;
  return /\b(code|pin)\b/.test(hay) && /\b(linking|verification|verify|pairing|auth)/.test(hay);
}

const SENSITIVE = [
  { type: "password", name: "password" },
  { type: "text", autocomplete: "one-time-code", name: "otp" },
  { type: "text", name: "code", placeholder: "8-digit linking code" },
  { type: "text", name: "code", placeholder: "Verification code" },
  { type: "text", name: "code", placeholder: "Pairing code" },
  { type: "text", name: "otp", placeholder: "Enter OTP" },
  { type: "text", name: "auth_code", placeholder: "Authentication code" },
  { type: "text", autocomplete: "cc-number", name: "card" },
  { type: "text", autocomplete: "cc-csc", name: "cvv" },
];
const NOT_SENSITIVE = [
  { type: "text", name: "promo", placeholder: "Promo code" },
  { type: "text", name: "postal", placeholder: "Postal code" },
  { type: "text", name: "zip", placeholder: "ZIP code" },
  { type: "text", name: "country_code", placeholder: "Country code" },
  { type: "text", name: "discount", placeholder: "Discount code" },
  { type: "text", name: "username", placeholder: "Username" },
  { type: "email", name: "email", placeholder: "Email" },
  { type: "text", autocomplete: "cc-exp", name: "expiry", placeholder: "MM/YY" },
];

let fail = 0;
for (const el of SENSITIVE) if (!isSensitiveField(el)) { console.log("FAIL should be sensitive:", JSON.stringify(el)); fail++; }
for (const el of NOT_SENSITIVE) if (isSensitiveField(el)) { console.log("FAIL should NOT be sensitive:", JSON.stringify(el)); fail++; }
console.log(fail === 0
  ? `PASS  ${SENSITIVE.length} sensitive + ${NOT_SENSITIVE.length} harmless fields classified correctly`
  : `${fail} FAILED`);
process.exit(fail === 0 ? 0 : 1);
