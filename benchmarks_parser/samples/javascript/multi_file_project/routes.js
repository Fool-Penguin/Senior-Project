// Application routes
const { SecurityFinding } = require('./models');
function setupRoutes(app) {
  app.get('/api/findings', (req, res) => {
    const finding = new SecurityFinding('F-101', 'CWE-89', 'CRITICAL');
    res.json([finding]);
  });
}
module.exports = { setupRoutes };
