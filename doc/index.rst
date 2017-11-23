CANopen for Python
==================

This package provides support for interacting with a network of CANopen_ nodes.

.. note::

    Most of the documentation here is directly stolen from the
    CANopen_ Wikipedia page.

    This documentation is a work in progress.
    Feedback and revisions are most welcome!

CANopen is a communication protocol and device profile specification for
embedded systems used in automation. In terms of the OSI model, CANopen
implements the layers above and including the network layer.
The CANopen standard consists of an addressing scheme, several small
communication protocols and an application layer defined by a device profile.
The communication protocols have support for network management, device
monitoring and communication between nodes, including a simple transport layer
for message segmentation/desegmentation.

Easiest way to install is to use pip_::

    $ pip install canopen


.. toctree::
   :maxdepth: 1

   network
   od
   nmt
   sdo
   pdo
   sync
   emcy
   timestamp
   lss
   integration
   profiles


.. _CANopen: https://en.wikipedia.org/wiki/CANopen
.. _pip: https://pip.pypa.io/en/stable/
