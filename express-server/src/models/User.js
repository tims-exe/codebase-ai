class User {
  constructor(id, name, email) {
    this.id = id;
    this.name = name;
    this.email = email;
  }

  // Static dummy data
  static allUsers() {
    return [
      new User(1, 'Alice', 'alice@example.com'),
      new User(2, 'Bob', 'bob@example.com'),
      new User(3, 'Charlie', 'charlie@example.com'),
    ];
  }

  static findById(id) {
    return User.allUsers().find(user => user.id === id);
  }
}

module.exports = User;