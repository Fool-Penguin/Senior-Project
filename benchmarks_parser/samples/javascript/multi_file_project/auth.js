// Auth module
const crypto = require('crypto');
function sanitizeInput(str) {
  // Prevent prototype pollution keys
  if (str === '__proto__' || str === 'constructor') return '';
  return String(str || '').trim();
}
module.exports = { sanitizeInput };
