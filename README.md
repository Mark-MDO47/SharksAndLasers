SharksAndLasers
Mark's Garage Door Closer Sharks and Lasers Project

![alt text](https://github.com/Mark-MDO47/SharksAndLasers/forFun/Board_AllTogether.png "Sharks & Lasers project mocked up")
![alt text](https://github.com/Mark-MDO47/SharksAndLasers/forFun/BondFigurines.png "James Bond figurines from Portugal via EBay")

This code supports a personal garage door monitor project for Mark Olson.
It involves lasers and light detectors to monitor garage door position.
The laser goes through a beam splitter and then to two light detector targets:
one is called "LaserCheck" and the other is called "Bond" (see below).
The LaserCheck should always be off when the laser is off and on when the laser
is on. The Bond should be off when the laser is off; when the laser is on and
the garage door is fully open Bond obstructs the laser and it is off; otherwise
Bond is on.

Also there are "hall effect" magnetic sensors; both off when the garage door is
in between else either HallSensorClosed or HallSensorOpen for full closed or open.

Additionally there is a light sensor for the garage opener light, which comes on
for a while whenever the garage door is operated.

There is an output for a relay that will either close or open the door. We try
to use all our sensors to be really sure we are closing the door and not opening.

There is a momentary contact self-destruct button which causes us to play a
self-destruct countdown on the "bomb" speaker - a small speaker in the shape
of a bomb. I don't know why these were ever manufactured but I found one at Fry's.
Frys.com 7073311 Manufacturer: DGL GROUP
UPC 822248838241 Model HY-527-WNK
See below for explanation of why we do this.

When we think the door is open we can close it and we can send an SMS text
message to some telephone numbers from a text file we read. We will only
try to close the door once but we may send periodic text messages; not sure
yet how I want that to work.

We log info to a Network Attached Storage NAS disk. We make efforts to
reconnect and write saved status lines if it goes offline for a while.

We create two simple web pages and try to keep the webserver operating
if we notice it died. The webpages give status. One for a cell phone,
one for a large screen.

why Bond?
Because where there are lasers, there must be sharks, and therefore there
must be sharks shooting lasers at James Bond, and there must be a self-destruct
button. That much is clear.

