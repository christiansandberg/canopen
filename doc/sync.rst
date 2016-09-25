Synchronization Object (SYNC)
=============================

The Sync-Producer provides the synchronization-signal for the Sync-Consumer.
When the Sync-Consumer receive the signal they start carrying out their
synchronous tasks.

In general, the fixing of the transmission time of synchronous PDO messages
coupled with the periodicity of transmission of the Sync Object guarantees that
sensor devices may arrange to sample process variables and that actuator devices
may apply their actuation in a coordinated fashion.

The identifier of the Sync Object is available at index 1005h.
