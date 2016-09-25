Process Data Object (PDO)
=========================

The Process Data Object protocol is used to process real time data among various
nodes. You can transfer up to 8 bytes (64 bits) of data per one PDO either from
or to the device. One PDO can contain multiple object dictionary entries and the
objects within one PDO are configurable using the mapping and parameter object
dictionary entries.

There are two kinds of PDOs: transmit and receive PDOs (TPDO and RPDO).
The former is for data coming from the device and the latter is for data going
to the device; that is, with RPDO you can send data to the device and with TPDO
you can read data from the device. In the pre-defined connection set there are
identifiers for four (4) TPDOs and four (4) RPDOs available.
With configuration 512 PDOs are possible.

PDOs can be sent synchronously or asynchronously. Synchronous PDOs are sent
after the SYNC message whereas asynchronous messages are sent after internal
or external trigger. For example, you can make a request to a device to transmit
TPDO that contains data you need by sending an empty TPDO with the RTR flag
(if the device is configured to accept TPDO requests).

With RPDOs you can, for example, start two devices simultaneously.
You only need to map the same RPDO into two or more different devices and make
sure those RPDOs are mapped with the same COB-ID.
