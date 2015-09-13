#!/usr/bin/python
# $Author: markdolson $ Mark Olson
# $Revision: 108 $
# $Date: 2015-09-11 12:47:08 -0700 (Fri, 11 Sep 2015) $
# $HeadURL: http://192.168.1.197/svn/mdoCode/trunk/SharksAndLasers/31_SharksAndLasers.py $
#
# This code was developed by Mark Olson in 2015. 
# It has been run on a Raspberry PI 2 but is by no means completely debugged.
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# This code supports a personal garage door monitor project for Mark Olson.
# It involves lasers and light detectors to monitor garage door position.
# The laser goes through a beam splitter and then to two light detector targets:
# one is called "LaserCheck" and the other is called "Bond" (see below).
# The LaserCheck should always be off when the laser is off and on when the laser
# is on. The Bond should be off when the laser is off; when the laser is on and
# the garage door is fully open Bond obstructs the laser and it is off; otherwise
# Bond is on.
#
# Also there are "hall effect" magnetic sensors; both off when the garage door is
# in between else either HallSensorClosed or HallSensorOpen for full closed or open.
#
# Additionally there is a light sensor for the garage opener light, which comes on
# for a while whenever the garage door is operated.
#
# There is an output for a relay that will either close or open the door. We try
# to use all our sensors to be really sure we are closing the door and not opening.
#
# There is a momentary contact self-destruct button which causes us to play a
# self-destruct countdown on the "bomb" speaker - a small speaker in the shape
# of a bomb. I don't know why these were ever manufactured but I found one at Fry's.
# Frys.com #7073311 Manufacturer: DGL GROUP
# UPC #822248838241 Model #HY-527-WNK
# See below for explanation of why we do this.
#
# When we think the door is open we can close it and we can send an SMS text
# message to some telephone numbers from a text file we read. We will only
# try to close the door once but we may send periodic text messages; not sure
# yet how I want that to work.
#
# We log info to a Network Attached Storage NAS disk. We make efforts to
# reconnect and write saved status lines if it goes offline for a while.
#
# We create two simple web pages and try to keep the webserver operating
# if we notice it died. The webpages give status. One for a cell phone,
# one for a large screen.
#
# why Bond?
# Because where there are lasers, there must be sharks, and therefore there
# must be sharks shooting lasers at James Bond, and there must be a self-destruct
# button. That much is clear.
#
#
debug = 1;
dbg_playmp3 = 1;
dbg_sendsms = 0;
dbg_refreshwebpage = 0;
#
#
from datetime import datetime;
import time;
import RPi.GPIO as GPIO
import subprocess
import os
import re; # regular expressions
#
time_interval = 6; # time between checks
time_threshold = 15; # DEBUGGING - 15 seconds to close garage door
sms_phone_one = "";
sms_phone_two = "";
#
# GPIO pin definitions - sensors
#   these are organized by individual sensors
#   for example: LaserBond, LaserCheck and OpenerLight are all LightDetect
#      but have individual pins
#
GPIO_gpio_LaserBond = 22;
GPIO_gpio_LaserCheck = 27;
GPIO_gpio_OpenerLight = 17;
GPIO_gpio_HallSensorClosed = 12;
GPIO_gpio_HallSensorOpen = 16;
GPIO_gpio_SelfDestruct = 25;
#
# GPIO sensor values that represent on
#   these are organized by sensor type
#   for example: LaserBond, LaserCheck and OpenerLight are all LightDetect
#
GPIO_ON_LightDetect = 1;
GPIO_ON_HallDetect = 0;
WIFI_NAS_ON_Detect = 1;
WIFI_HTTP_ON_Detect = 1;
GPIO_ON_SelfDestruct = 0;
#
# GPIO pin definitions - outputs
#   these are organized by individual outputs
#   for example: RELAY1 and RELAY2 are relay outputs
#      but have individual pins
#
GPIO_gpio_RELAY1 = 23;
GPIO_gpio_RELAY2 = 24;
GPIO_gpio_LASER = 4;
#
# GPIO output value definitions
#   these are organized by output type
#   for example: RELAY1 and RELAY2 are relay outputs
#
GPIO_ENERGIZE_RELAY = 1;
GPIO_DE_ENERGIZE_RELAY = 0;
GPIO_ENERGIZE_LASER = 1;
GPIO_DE_ENERGIZE_LASER = 0;
#
# sensor status
#
#   Concept: if James blocks laser, garage door is open
#   we use beamsplitter and laser check so
#       can detect malfunction or bad aiming
#   light sensors (actually any GPIO, but only makes sense
#       for laser-detect)) can be sensed with
#       laser-ON or laser-OFF to determine if they are
#       malfunctioning.
#   independently: hall sensors also detect garage door position
#
#   the raw I/O value (ex: GPIO) is not stored in this table
#   the val-canonical is "1" if raw I/O val == ON-val; otherwise "0"
#   there is a nominal NOM-val that is also canonical
#
#   for example, the HallSensorClosed is nominally true or 1, while
#       the HallSensorOpen is nominally false or 0.
#
# format is as follows:
#    name, val-canonical, IO-type, IO-gpio, ON-val, NOM-val, OffsetTop, OffsetLeft
#
status_list = [ 
    'Bond_laser_on', 101, 'LASER_ON_GPIO', GPIO_gpio_LaserBond, GPIO_ON_LightDetect, 1, 400, 260,
    'LaserCheck_laser_on', 101, 'LASER_ON_GPIO', GPIO_gpio_LaserCheck, GPIO_ON_LightDetect, 1, 280, 160,
    'Bond_laser_off', 101, 'GPIO', GPIO_gpio_LaserBond, GPIO_ON_LightDetect, 0, 400, 320,
    'LaserCheck_laser_off', 101, 'GPIO', GPIO_gpio_LaserCheck, GPIO_ON_LightDetect, 0, 280, 220,
    'HallSensorClosed', 101, 'GPIO', GPIO_gpio_HallSensorClosed, GPIO_ON_HallDetect, 1, 90, 160,
    'HallSensorOpen', 100, 'GPIO', GPIO_gpio_HallSensorOpen, GPIO_ON_HallDetect, 0, 210, 160,
    'OpenerLight', 100, 'GPIO', GPIO_gpio_OpenerLight, GPIO_ON_LightDetect, 0, 1, 160,
    'NASavailable', 101, 'WIFI_NAS', 'WIFI_NAS', WIFI_NAS_ON_Detect, 1, 210, 340,
    'HTTPavailable', 101, 'WIFI_HTTP', 'WIFI_HTTP', WIFI_HTTP_ON_Detect, 1, 210, 400,
    'SelfDestruct', 101, 'GPIO', GPIO_gpio_SelfDestruct, GPIO_ON_SelfDestruct, 0, 20, 280 ];
#
status_numElements = 8;
status_entryName = 0;
status_entryVal = 1;
status_entryType = 2;
status_entryIONUM = 3;
status_entryOnVal = 4;
status_entryNominalVal = 5;
status_entryHtmlTop = 6;
status_entryHtmlLeft = 7;
#
# compare_list
#
# an entry in a "compare" is just a name from the status list followed by a canonical value to compare
# there can be one or more of these entries in each "compare"
#
# the "list of compares" helps loop through producing all the status strings. Each compare is placed int
#    the compare list, along with a string to put into status string if all the compare entries
#    compare succesfully.
#
compare_numElements = 2;
compare_entryName = 0;
compare_entryVal = 1;
compare_quiet = [
    'OpenerLight', 0];
compare_active = [
    'OpenerLight', 1];
compare_open = [
    'Bond_laser_on', 0,
    'LaserCheck_laser_on', 1,
    'Bond_laser_off', 0,
    'LaserCheck_laser_off', 0,
    'HallSensorClosed', 0,
    'HallSensorOpen', 1];
compare_closed = [
    'Bond_laser_on', 1,
    'LaserCheck_laser_on', 1,
    'Bond_laser_off', 0,
    'LaserCheck_laser_off', 0,
    'HallSensorClosed', 1,
    'HallSensorOpen', 0];
compare_moving = [
    'Bond_laser_on', 1,
    'LaserCheck_laser_on', 1,
    'Bond_laser_off', 0,
    'LaserCheck_laser_off', 0,
    'HallSensorClosed', 0,
    'HallSensorOpen', 0];
compare_NAS_good = [
    'NASavailable', 1];
compare_NAS_bad = [
    'NASavailable', 0];
compare_HTTP_good = [
    'HTTPavailable', 1];
compare_HTTP_bad = [
    'HTTPavailable', 0];
compare_SelfDestruct = [
    'SelfDestruct', 1];
compare_closed_fail = [
    'HallSensorClosed', 1,
    'HallSensorOpen', 0,
    'LaserCheck_laser_on', 0];
compare_open_fail = [
    'HallSensorClosed', 0,
    'HallSensorOpen', 1,
    'LaserCheck_laser_on', 0];
compare_lasercheckON_fail = [
    'LaserCheck_laser_on', 0];
compare_laserbondoff_fail = [
    'Bond_laser_off', 1];
compare_lasercheckOFF_fail = [
    'LaserCheck_laser_off', 1];
compare_hallsensorinconsistent_fail = [
    'HallSensorClosed', 1,
    'HallSensorOpen', 1];
#
# here is the list of compares.
#
list_of_compares_numElements = 2;
list_of_compares_List = 0;
list_of_compares_Name = 1;
list_of_compares = [
    compare_open, 'Open',
    compare_closed, 'Closed',
    compare_moving, 'Moving',
    compare_open_fail, 'Open',
    compare_closed_fail, 'Closed',
    compare_lasercheckON_fail, 'LaserCheckOnFail',
    compare_laserbondoff_fail, 'LaserBondOffFail',
    compare_lasercheckOFF_fail, 'LaserCheckOffFail',
    compare_hallsensorinconsistent_fail, 'HallSensorsInconsistentFail',
    compare_quiet, 'Quiet',
    compare_active, 'Active',
    compare_NAS_good, 'NAS-Online',
    compare_NAS_bad, 'NAS-Offline',
    compare_HTTP_good, 'HTTP-Online',
    compare_HTTP_bad, 'HTTP-Offline',
    compare_SelfDestruct, 'SelfDestruct'];

#
# initialize_HW()
#
# Make sure the GPIO pins are ready:
# Use GPIO numbers (BCM) not pin numbers (BOARD)
#
# initialize sound hardware
#
# read SMS phone numbers
#
def initialize_HW():
    global sms_phone_one;
    global sms_phone_two;
    #
    if (0 != debug):
        print("initialize_HW() called");
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # outputs
    GPIO.setup(GPIO_gpio_RELAY1, GPIO.OUT)
    GPIO.output(GPIO_gpio_RELAY1, GPIO_DE_ENERGIZE_RELAY) # RELAY1 OFF
    GPIO.setup(GPIO_gpio_RELAY2, GPIO.OUT)
    GPIO.output(GPIO_gpio_RELAY2, GPIO_DE_ENERGIZE_RELAY) # RELAY2 OFF
    GPIO.setup(GPIO_gpio_LASER, GPIO.OUT)
    GPIO.output(GPIO_gpio_LASER, GPIO_DE_ENERGIZE_LASER) # LASER OFF
    # inputs
    GPIO.setup(GPIO_gpio_LaserBond, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(GPIO_gpio_LaserCheck, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(GPIO_gpio_OpenerLight, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(GPIO_gpio_HallSensorClosed, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(GPIO_gpio_HallSensorOpen, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(GPIO_gpio_SelfDestruct, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    # sound
    batcmd = 'amixer cset numid=3 1';
    my_ignore = subprocess.check_output(batcmd, stderr=subprocess.STDOUT, shell=True);
    # sms - I read two phone numbers.
    sms_phone = open("/home/pi/mdo/sms_phones.txt", "r");
    input = sms_phone.readline();
    sms_phone_one = input.rstrip('\r\n');
    input = sms_phone.readline();
    sms_phone_two = input.rstrip('\r\n');
    sms_phone.close();
    re_phonenum = re.compile(r"^\d\d\d\d\d\d\d\d\d\d[@][A-Za-z0-9.]+$");
    if (re_phonenum.match(sms_phone_one) == None):
        print("ERROR: BAD SMS Phone Number one: %s" % sms_phone_one);
        sms_phone_one = "";
    if (re_phonenum.match(sms_phone_two) == None):
        print("ERROR: BAD SMS Phone Number two: %s" % sms_phone_two);
        sms_phone_two = "";
    if (0 != debug):
        print("Phone Numbers:\n%s\n%s" % (sms_phone_one, sms_phone_two));

#
# play_mp3(filename)
#
# plays the named mp3 file
#
def play_mp3(filename):
    if (0 != dbg_playmp3):
        # play the file
        os.system('omxplayer %s' % filename);
    if (0 != debug):
        print("Playing MP3 file %s" % filename);

#
# send_sms(date_time, text)
#
# sends SMS text message to the two phones previously loaded
#
# if a phone is correctly loaded, it will have an "@" in the text
#
# to send a text message from Raspberry Pi on WiFi we need email.
#    sudo apt-get install ssmtp mailutils mpack
# Now edit the file /etc/ssmtp/ssmtp.conf as root and add the next lines.
# Please note that some of the lines already exist and may need to be changed.
# Others don't exist yet and need to be added to the end of the file.
#    mailhub=smtp.gmail.com:587
#    hostname=ENTER YOUR RPI'S HOST NAME HERE
#    AuthUser=YOU@gmail.com
#    AuthPass=PASSWORD
#    useSTARTTLS=YES
# Again you'll have to replace YOU with your gmail login name and PASSWORD
# with your (application specific) gmail password. After this you're done.
# You don't even have to restart the SSMTP server (in fact, there is none).
#
# an ATT text message can be sent to <10-digit-phone-num>@text.att.net
#

def send_sms(date_string, sms_text):
    if (0 != debug):
        print("send_sms(%s)" % sms_text);
    if (0 != dbg_sendsms):
        if (sms_phone_one.find("@") > 0):
            batcmd = 'echo "%s" | mail %s' % (sms_text, sms_phone_one);
            my_ignore = subprocess.check_output(batcmd, stderr=subprocess.STDOUT, shell=True);
            action_string = "SENDING SMS TEXT MESSAGE PHONE ONE: %s" % sms_text;
            save_log_entry(date_string, action_string);
            if (0 != debug):
                print(action_string);
        if (sms_phone_two.find("@") > 0):
            batcmd = 'echo "%s" | mail %s' % (sms_text, sms_phone_two);
            my_ignore = subprocess.check_output(batcmd, stderr=subprocess.STDOUT, shell=True);
            action_string = "SENDING SMS TEXT MESSAGE PHONE TWO: %s" % sms_text;
            save_log_entry(date_string, action_string);
            if (0 != debug):
                print(action_string);

#
# close_garage(date_time, text)
#
def close_garage(date_string, action_string):
    save_log_entry(date_string, action_string);
    if (0 != debug):
        print(action_string);
    GPIO.output(GPIO_gpio_RELAY1, GPIO_ENERGIZE_RELAY); # RELAY1 ON
    time.sleep(0.1);
    GPIO.output(GPIO_gpio_RELAY1, GPIO_DE_ENERGIZE_RELAY); # RELAY1 OFF
    send_sms(date_string, "Sharks and Lasers closed garage door %s" % date_string);

#
# get_GPIO_input(gpio, ONval)
#
# returns 1 (ON) or 0 (OFF)
#     ONval used to convert raw I/O to canonical ON/OFF (true/false)
#
def get_GPIO_input(gpio, ONval):
    val = GPIO.input(gpio);
    if (val == ONval):
        val = 1;
    else:
        val = 0;
    return val;

#
# ping_WIFI_NAS()
#
# returns one if the ping works, else zero
#
def ping_WIFI_NAS():
    my_return = 0;
    
    try:
        my_result = subprocess.check_output('ping -c1 192.168.1.195', stderr=subprocess.STDOUT, shell=True);
        if (my_result.find("1 packets transmitted, 1 received, 0% packet loss") != -1):
            my_return = 1;
    except subprocess.CalledProcessError:
        # exception raised when ping does not work & returns non-zero code
        my_return = 0;
    return my_return;

#
# get_WIFI_HTTP_status(ignored)
#
# returns one if the http server is running else zero
#
def get_WIFI_HTTP_status(ignored):
    my_return = 0;

    my_result = subprocess.check_output('/bin/ps -AF', stderr=subprocess.STDOUT, shell=True);
    # we are searching for '##:##:## python -m SimpleHTTPServer'
    #   don't be fooled by '##:##:## sudo python -m SimpleHTTPServer'
    re_simplehttpserver = re.compile(r":\d\d[   ]*python -m SimpleHTTPServer", re.MULTILINE);
    for match in re_simplehttpserver.finditer(my_result):
        my_return = 1;
    return my_return;

#
# get_WIFI_NAS_status(ignored)
#
# returns 1 if NAS is mounted, which implies WIFI is on
# else returns 0
#
# requires that cifs-utils is installed; default on newer Raspberry Pi
#    to check if installed, do 'dpkg -s cifs-utils'
#       look for something like 'Status: install ok installed'
#    otherwise need to install it with 'sudo apt-get install cifs-utils'
#
# if ping finds NAS but mount does not, we do 'mount -a'
#    our mount point is as below in /etc/fstab so 'mount -a' will mount it (note: ... is long path)
#      //192.168.1.195/media/.../logs /media/networkshare/NAS cifs guest,uid=1000,gid=1000,iocharset=utf8 0 0
#
# once NAS is up and running, we check on HTTP server and restart if needed
#
mount_delay = 0; # time to wait before trying 'mount -a' command again
http_delay = 0; # time to wait before trying restart of http simple server again
def get_WIFI_NAS_status(str):
    global mount_delay;
    global http_delay;

    if (1 == ping_WIFI_NAS()):
        my_result = subprocess.check_output('mount', stderr=subprocess.STDOUT);
        # we are searching for a mount point for SharksAndLasers
        if (my_result.find("SharksAndLasers") != -1):
            my_return = 1;
            mount_delay = 0;
        else:
            my_return = 0;
            if (mount_delay <= 0):
                os.system('sudo mount -a &');
                mount_delay = (10 + time_interval -1) // time_interval; # wait at least 10 secs before trying again
            elif (mount_delay > 0):
                mount_delay -= 1;
    else:
        my_return = 0;
        mount_delay = 0;

    if (my_return > 0):
        # we only mess with HTTP server once the NAS logging is up and running
        if (http_delay <= 0):
            if (0 == get_WIFI_HTTP_status('ignored')):
                if (debug):
                    print("RESTARTING SimpleHTTPServer");
                os.system('cd /home/pi/mdo/html ; sudo python -m SimpleHTTPServer 80 >/dev/null 2>&1 &');
            else:
                if (debug):
                    print("ALREADYRUNNING SimpleHTTPServer");
            http_delay = (120 + time_interval -1) // time_interval; # wait at least 120 secs before checkingagain
        elif (http_delay > 0):
            http_delay -= 1;
        
    return (my_return);

#
# get_indiv_statuses(the_status)
#
#    param: the status list
#
#    loops through the status list, doing the raw I/O then converting the raw I/O values to canonical values
#        and storing the current values back into the status list.
#
#    returns: 0 if good, non-zero if fail
#         updates status value for all items in list
#
def get_indiv_statuses(the_status):
   my_status = 0; # good
   for ndx in range(0, len(the_status), status_numElements):
      if (the_status[ndx+status_entryType] == 'GPIO'):
           val = get_GPIO_input(the_status[ndx+status_entryIONUM], the_status[ndx+status_entryOnVal]);
           if (debug > 0):
               print("         Indiv %s GPIO: GPIOnum=%d val=%d nom=%d" % (the_status[ndx+status_entryName], the_status[ndx+status_entryIONUM], val, the_status[ndx+status_entryNominalVal]));
      elif (the_status[ndx+status_entryType] == 'LASER_ON_GPIO'):
           GPIO.output(GPIO_gpio_LASER, GPIO_ENERGIZE_LASER) # LASER ON
           time.sleep(0.5); # let things settle a bit
           val = get_GPIO_input(the_status[ndx+status_entryIONUM], the_status[ndx+status_entryOnVal]);
           if (debug > 0):
               print("         Indiv %s LASER_ON_GPIO: GPIOnum=%d val=%d nom=%d" % (the_status[ndx+status_entryName], the_status[ndx+status_entryIONUM], val, the_status[ndx+status_entryNominalVal]));
           GPIO.output(GPIO_gpio_LASER, GPIO_DE_ENERGIZE_LASER) # LASER OFF
           time.sleep(0.5); # let things settle a bit
      elif (the_status[ndx+status_entryType] == 'WIFI_NAS'):
           val = get_WIFI_NAS_status(the_status[ndx+status_entryIONUM]);
           if (debug > 0):
               print("         Indiv %s WIFI: IOnum=%s val=%s nom=%s" % (the_status[ndx+status_entryName], the_status[ndx+status_entryIONUM], val, the_status[ndx+status_entryNominalVal]));
      elif (the_status[ndx+status_entryType] == 'WIFI_HTTP'):
           val = get_WIFI_HTTP_status(the_status[ndx+status_entryIONUM]);
           if (debug > 0):
               print("         Indiv %s HTTP: IOnum=%s val=%s nom=%s" % (the_status[ndx+status_entryName], the_status[ndx+status_entryIONUM], val, the_status[ndx+status_entryNominalVal]));
      else:
           if (debug > 0):
               print("ERROR - %s unknown status I/O Type %s\n" % (the_status[ndx+status_entryName], the_status[ndx+status_entryType]));
           val = -999;
           my_status = -1; # bad
      the_status[ndx+status_entryVal] = val;
   return my_status;

#
# get_one_overall_status(the_status, the_compare)
#
#    param: the status list
#           the "compare" to check
#
#    loops through the status list, checking each entry versus the "compare".
#
#    returns: "1" if all "compare" items satisfied; else "0"
#
def check_one_overall_status(the_status, the_compare):
   my_compare = 1; # true until mismatch
   for ndx in range(0, len(the_status), status_numElements):
      if (1 == my_compare):
          for cmp in range(0, len(the_compare), compare_numElements):
              if (the_status[ndx+status_entryName] == the_compare[cmp+compare_entryName]):
                  # if (debug > 0):
                      # print("     One: %s status: %s compare: %s" % (the_status[ndx+status_entryName], the_status[ndx+status_entryVal], the_compare[cmp+compare_entryVal]));
                  if (the_compare[cmp+compare_entryVal] != 'NA') and (the_status[ndx+status_entryVal] != the_compare[cmp+compare_entryVal]):
                       # if (debug > 0):
                           # print("     One: compare failed");
                       my_compare = 0;
                  break;
   return my_compare;


#
# get_overall_status(the_status)
#
#    param: the status list
#
#    loops through the list of "compares", inserting compare text if entire compare is satisfied
#
#    returns: textual status. Elements are separated by "|"
#
# example return " Closed | Quiet | NAS-Online"
#
def get_overall_status(the_status):
   my_status = "";
   num_status = 0;
   for ndx in range(0, len(list_of_compares), list_of_compares_numElements):
       tmp = check_one_overall_status(the_status, list_of_compares[ndx+list_of_compares_List]);
       # if (debug > 0):
           # print("  Overall: %s %d" % (list_of_compares[ndx+list_of_compares_Name], tmp));
       if (1 == tmp):
           if (0 != num_status):
               my_status += ' | ';
           my_status += list_of_compares[ndx+list_of_compares_Name];
           num_status += 1;

   return(my_status);

#
# save_log_entry(date_string, status_string)
#
# creates/appends log file and saves some lines internally for web page
#
# this routine will internally save up to 100 log lines until it sees "NAS-Online" and then append
#    all saved lines to the NAS logfile
#
loglines_num = 100;
loglines_num2write = 0;
loglines_ndx = 0;
loglines = [""] * 100;
loglines_prev_status_string = "";
#
def save_log_entry(date_string, status_string):
    global loglines_num;
    global loglines_num2write;
    global loglines_ndx;
    global loglines;
    global loglines_prev_status_string;
    if (loglines_prev_status_string != status_string):
        if (0 != debug):
            print("SAVE_LOG_ENTRY save new status %s %s" % (date_string, status_string));
        loglines[loglines_ndx] = "%s %s" % (date_string, status_string);
        loglines_ndx = (loglines_ndx + 1) % loglines_num;
        loglines_num2write = min(loglines_num2write+1, loglines_num);
        loglines_prev_status_string = status_string;
    if ((0 != loglines_num2write) and (status_string.find("NAS-Online") > 0)):
        if (0 != debug):
            print("SAVE_LOG_ENTRY write %d lines" % loglines_num2write);
        logfile = open("/media/networkshare/NAS/SharksAndLasersLogFile.txt", "a");
        ndx = (loglines_ndx - loglines_num2write + loglines_num) % loglines_num;
        while (ndx != loglines_ndx):
            logfile.write("%s\n" % loglines[ndx]);
            ndx = (ndx + 1) % loglines_num;
        logfile.close();
        loglines_num2write = 0;
    return 0;
#
# write_html(lots-of-parameters)
#
# probably should go ahead and use globals instead of all these parameters
#
# somewhat complicated and idiosyncratic routine that produces web pages that are useful for me.
# feel free to replace it.
#
# writes two HTML files; one for smartphone and one for PC
# NOTE: previous implementation that opened both output files at once got permissions problem on HTML file: root ownership
#
# web pages are served by the following daemon (uses compatible Bash syntax for redirect):
#   cd <place where html files etc. are stored>
#   sudo python -m SimpleHTTPServer 80 >/dev/null 2>&1 &
# the webserver will be restarted automatically when checking WIFI status if needed
#
# globals are the log lines; didn't want to add more parameters
#
def write_html(the_status, my_curr_string, my_status_curr, my_prev_string, my_status_prev, my_delta_secs, my_time_interval):
    global loglines_num;
    global loglines_ndx;
    global loglines;
    num_web_lines = 20; # number to display on web pages
    #
    HTML = open("/home/pi/mdo/html/big.html", "w");
    if (0 != dbg_refreshwebpage): # to make web pages auto-refresh
        HTML.write("<head><meta http-equiv=\"refresh\" content=\"%d\"></head>\n" % my_time_interval);
    HTML.write("<html><body>\n<B>Olson Sharks and Lasers</B><br>\n");
    HTML.write("<A href=./index.html>Click for Small Version</A><br>\n");
    HTML.write("Curr Date %s Curr Status = %s<br>\n" % (my_curr_string, my_status_curr));
    HTML.write("Prev Date %s Prev Status = %s<br>\n" % (my_prev_string, my_status_prev));
    HTML.write("    Time at current status is %1.0f seconds<br>\n" % my_delta_secs);
    HTML.write("<div style=\"position:relative; left:0; top:20;\">\n");
    HTML.write("  <img src=\"images/SharksAndLasersPlan.png\" style=\"position:relative; top:0; left:0;\"/>\n");
    for ndx in range(0, len(the_status), status_numElements):
        if (the_status[ndx+status_entryVal] == the_status[ndx+status_entryNominalVal]):
            HTML.write("  <img src=\"images/CHECK.png\" style=\"position:absolute; top:%d; left:%d;\"/>\n" % (the_status[ndx+status_entryHtmlTop], the_status[ndx+status_entryHtmlLeft]));
        else:
            HTML.write("  <img src=\"images/ECKS.png\" style=\"position:absolute; top:%d; left:%d;\"/>\n" % (the_status[ndx+status_entryHtmlTop], the_status[ndx+status_entryHtmlLeft]));
    HTML.write("</div><br>\n");
    # go backward for num_web_lines entries
    ndx = (loglines_ndx - 1 + loglines_num) % loglines_num;
    end_ndx = (loglines_ndx - num_web_lines - 1 + loglines_num) % loglines_num;
    HTML.write("<B>LOG FILE ENTRIES</B><br><br>\n");
    while (ndx != end_ndx):
        HTML.write("%s<br>\n" % loglines[ndx]);
        ndx = (ndx - 1 + loglines_num) % loglines_num;
    HTML.write("</html></body>\n");
    HTML.close();

    html = open("/home/pi/mdo/html/index.html", "w");
    if (0 != dbg_refreshwebpage): # to make web pages auto-refresh
        html.write("<head><meta http-equiv=\"refresh\" content=\"%d\"></head>\n" % my_time_interval);
    html.write("<html><body>\n<B>Olson Sharks and Lasers</B><br>\n");
    html.write("<A href=./big.html>Click for Big Version</A><br>\n");
    html.write("Curr Date %s Curr Status = %s<br>\n" % (my_curr_string, my_status_curr));
    html.write("Prev Date %s Prev Status = %s<br>\n" % (my_prev_string, my_status_prev));
    html.write("    Time at current status is %1.0f seconds<br>\n" % my_delta_secs);
    html.write("<br>\n");
    for ndx in range(0, len(the_status), status_numElements):
        if (the_status[ndx+status_entryVal] == the_status[ndx+status_entryNominalVal]):
            html.write("  indiv: nominal %s status %s<br>\n" % (the_status[ndx+status_entryName], the_status[ndx+status_entryVal]));
        else:
            html.write("  indiv: OFF-NOM %s status %s<br>\n" % (the_status[ndx+status_entryName], the_status[ndx+status_entryVal]));
    # go backward for num_web_lines entries
    ndx = (loglines_ndx - 1 + loglines_num) % loglines_num;
    end_ndx = (loglines_ndx - num_web_lines - 1 + loglines_num) % loglines_num;
    html.write("<br><B>LOG FILE ENTRIES</B><br><br>\n");
    while (ndx != end_ndx):
        html.write("%s<br>\n" % loglines[ndx]);
        ndx = (ndx - 1 + loglines_num) % loglines_num;
    html.write("</html></body>\n");
    html.close();

#
#  MAIN FLOW - Sharks and Lasers
#
initialize_HW();
dt_prev = datetime.now();
dt_prev_string = dt_prev.strftime("%Y-%m-%d %H:%M:%S");
status_prev = "SHARKS AND LASERS BOOTING UP";
save_log_entry(dt_prev_string, status_prev);
try:  
    while (1):
        time.sleep(time_interval);
        dt_curr = datetime.now();
        dt_curr_string = dt_curr.strftime("%Y-%m-%d %H:%M:%S");
        if (debug > 0):
            print("datestring = %s" % dt_curr_string);
        #
        get_indiv_statuses(status_list);
        if (debug > 0):
            print("got individual");
        #
        # Get overall status in text
        #   also time we have been in this status
        #
        status_curr = get_overall_status(status_list);
        if (debug > 0):
            print("status_curr = %s" % status_curr);
        save_log_entry(dt_curr_string, status_curr);
        if (status_curr != status_prev):
            dt_delta = dt_curr - dt_curr;
        else:
            dt_delta = dt_curr - dt_prev;
        delta_secs = dt_delta.days*86400 + dt_delta.seconds;
        #
        # write big and small web status pages
        #
        write_html(status_list, dt_curr_string, status_curr, dt_prev_string, status_prev, delta_secs, time_interval);
        #
        # update time calculations for next time through
        #
        if (status_curr != status_prev):
            dt_prev = dt_curr;
            dt_prev_string = dt_curr_string;
        status_prev = status_curr;
        #
        # take any actions needed
        #
        if ((-1 != status_curr.find('Open')) and (delta_secs > time_threshold)):
            action_string = "CLOSING GARAGE DOOR AFTER %d SECONDS" % delta_secs;
            close_garage(dt_curr_string, action_string);
except KeyboardInterrupt:
    # put here any code to run before the program
    # exits when you press CTRL+C
    print("CTRL-C - exiting");
# except:
    # this catches ALL other exceptions including errors.
    # There won't be any error messages for debugging
    # so only use it once the code is working
    # print("Unexpected error or exception occurred - exiting");
finally:
    GPIO.output(GPIO_gpio_RELAY1, GPIO_DE_ENERGIZE_RELAY); # RELAY1 OFF
    GPIO.output(GPIO_gpio_RELAY2, GPIO_DE_ENERGIZE_RELAY); # RELAY2 OFF
    GPIO.output(GPIO_gpio_LASER, GPIO_DE_ENERGIZE_LASER) # LASER OFF
    GPIO.cleanup() # this ensures a clean exit
    if (1 == debug):
         print("GPIO.cleanup() exit");
