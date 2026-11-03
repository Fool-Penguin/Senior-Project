// Database connector module
class DatabaseClient {
  constructor(uri) {
    this.uri = uri;
    this.connected = false;
  }
  async connect() {
    this.connected = true;
    return this;
  }
}
module.exports = { DatabaseClient };
