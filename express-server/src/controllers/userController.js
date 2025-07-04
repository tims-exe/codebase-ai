const User = require('../models/User');

exports.getAllUsers = (req, res) => {
  const users = User.allUsers();
  res.json({ data: users });
};

exports.getUserById = (req, res) => {
  const id = parseInt(req.params.id, 10);
  const user = User.findById(id);
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }
  res.json({ data: user });
};