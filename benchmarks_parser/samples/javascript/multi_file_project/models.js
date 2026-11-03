// Model entities
class SecurityFinding {
  constructor(id, cwe, severity) {
    this.id = id;
    this.cwe = cwe;
    this.severity = severity;
    this.timestamp = Date.now();
  }
}
module.exports = { SecurityFinding };
