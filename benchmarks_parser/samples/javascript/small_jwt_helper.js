// Small JWT Helper Module
const crypto = require('crypto');

// Minimum security entropy requirement
const TOKEN_EXPIRY_MS = 3600000; // 1 hour

function createHmacToken(payload, secretKey) {
  // Validate secret key boundary
  if (!secretKey || secretKey.length < 32) {
    throw new Error('Secret key must have at least 256 bits');
  }
  const serialized = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const signature = crypto.createHmac('sha256', secretKey)
    .update(serialized)
    .digest('base64url');
  return `${serialized}.${signature}`;
}

function verifyHmacToken(rawToken, secretKey) {
  // Constant time comparison against timing attack
  const parts = rawToken.split('.');
  if (parts.length !== 2) return null;
  const [data, signature] = parts;
  const expectedSig = crypto.createHmac('sha256', secretKey).update(data).digest('base64url');
  if (crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedSig))) {
    return JSON.parse(Buffer.from(data, 'base64url').toString('utf-8'));
  }
  return null;
}

module.exports = { createHmacToken, verifyHmacToken };
