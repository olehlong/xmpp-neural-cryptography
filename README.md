xmpp-neural-cryptography
========================

XMPP client with neural cryptography using [Tree Parity Machines](http://en.wikipedia.org/wiki/Neural_cryptography). It's very basic XMPP client that used to demonstrate algorithm. Developed for my diploma and free to use.

Key exchange protocol algorithm was improoved to reduce amount of transmitted messages between two clients. Both clients are generating input vectors and sending them with other information to another Tree Parity Machine (weights hash, output, etc.). It twice reduces amount of transmitted messages and Tree Parity Machines synchronization goes much faster.

Requirements:

1. sqlite
2. python-gtk
3. [sleekxmpp](https://github.com/fritzy/SleekXMPP)
4. numpy
