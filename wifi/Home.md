## Background

This project uses Arduino to reset the chip inside your Canon printer's MC-G02 Maintenance Cartridge, so that bring the chip back to a like-new status, and reuse the cartridge again and again.

#### What is Maintenance Cartridge

Maintenance Cartridge is a cartridge inside some printers, not limited to Canon, it's the place where the "wasted inks" are stored. This cartridge will eventually become full, and your printer will refuse to print any more. Then normally you have to buy a new one from Canon.

#### What is MC-G02

MC-G02 is one type of Maintenance Cartridge used inside the recent Canon PIXMA G series printers，including:

US Version: G620/G1220/G2260/G3260

Chinese Version: G580/G680/G1820/G2820/G2860/G3820/G3860

(and other versions in other countries..)

#### What Stops you from reusing the MC-G02 Maintenance Cartridge

You can detach the MC-G02 cartridge printer pretty easily, and you can clean it by yourself and remove the accumulated ink inside. Canon doesn't use a sensor to detect how much ink is indeed inside the cartridge; instead there is a chip on the cartridge, which behaves as a "counter", and gets increased each time the cartridge is used. Even if you have cleaned wasted ink inside the cartridge, the counter inside the chip won't decrease, and the printer will still refuse to print.

#### Back to this Project

This project allows you to "reset" the counter inside the chip mentioned above. Then you can reuse the MC-G02 cartridge.

## Usage

#### Prerequisite
To use this project, you need:

Know basic usage of Arduino, like upload program to Arduino and run, read output from Serial Monitor.

Remove the chip from the cartridge and connect it to Arduino.

#### Overview

This project consists of a read(dump) program and a write program.

The write program is literally the resetter of the chip. But in order to use the write program, you need a rom. 

To get a rom, you need either:
1. get it from someone else who already did the dump, maybe on the internet.
2. dump a rom by yourself. 

The dumped rom just allows you to set the cartridge back to exactly the same status as the time the rom is dumped, thus can be used to reset the cartridge. So if you want to dump it by yourself, do it early, before your cartridge is filled up.

#### Connect the chip to arduino

Detach the cartridge from the printer, remove the chip from the cartridge, and connect the wires.

<img src="https://github.com/wangyu-/canon_mc-g02_resetter/blob/90f3febe345bee0e14daf593a8b206829f14307f/images/wire1.png" width="400">
<img src="https://github.com/wangyu-/canon_mc-g02_resetter/blob/90f3febe345bee0e14daf593a8b206829f14307f/images/wire2.png" width="390">
<img src="https://github.com/wangyu-/canon_mc-g02_resetter/blob/90f3febe345bee0e14daf593a8b206829f14307f/images/wire3.png" width="340">

Those two resistors are of 10k ohm, used as "pull-up" resistors. The circuit is suggested by [1].

#### Dump the rom (if you can't get a rom from others)

Open the program inside `arduino/sketch_hack_read` with Arduino IDE, upload it to Arduino and run. 

If everything is as expected, you will get the following output from Serial Monitor (use baud rate `9600`):
 
```
Start Dumping...
Below is your rom:

const unsigned char my_rom1[] PROGMEM=
{
0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,...,
...
...
}
```

Then the `{0xXX,0xXX,0xXX,0xXX,...}` stuff is the rom you dumped.  Each 0xXX represents a byte, you should get 2048 such bytes. Since the chip is an eeprom of 16Kbits. Save this for future use, better with the `const unsigned char my_rom1[] PROGMEM=` prefix, so that it can be copied as a whole conveniently.

If you get something else such as `Wire Not Ready!!!`, then there must be something wrong. (e.g. your wire is not correctly or solidly connected).

##### Note

It's <del>suggested</del> mandatory to dump it 2 times, and make sure the 2 dumps are identical, in case you get a corrupted dump.

##### Note2

It's strongly suggested to upload the `arduino/sketch_hack_read` program to your Arduino before you connect the cartridge chip into the circuit. So that you are sure at the moment you connect your chip, the program running on arduino is indeed the correct one.

#### Write the dumped rom to chip

Open the program inside `arduino/sketch_hack_write` with Arduino IDE,  You copy the whole `const unsigned char my_rom1[] PROGMEM={0xXX,0xXX,0xXX,0xXX,...}`,  and paste it into the correct place of the program opened in Arduino IDE(there is an indicator to help you locate the place).


upload it to Arduino and run. If everything is as expected, you will get the following output from Serial Monitor (baud rate 9600):

```
Start Writing Rom...
current writing page:0
current writing page:16
......
current writing page:112

Write Done!

Start Dumping for Verification...
Check if this dump matches with before by yourself:

const unsigned char my_rom1[] PROGMEM=
{
0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,0xXX,...,
...
...
}
```

The program first writes the dumped rom into the chip, and then starts a verification dump. You at least need to do a fast eyeball check of the value: the verification dump should be identical to the rom you used for writing.  For extra safety, it's suggested to make sure those values are identical by some diff tools (e.g. `vimdiff`).

##### Note

Both the read program and write program used [2] [3] as reference during writing.

#### All Done.

Your cartridge chip is now "resetted". Insert the chip back to the cartridge and attach the cartridge into the printer.  (You possibly want to clean/dry the wasted inks inside before reusing the cartridge.)


## Q/A

#### Q: Why don't you (the author) share a dumped rom, so that I don't need to dump it by myself.
A: That content dumped from Cannon chip might has some kind of copyright, sharing it might involve me into legal trouble. So, sorry I can't shared. Get one by yourself. Possibly from your or your friend's cartridge before it's used up, or from internet.

#### Q: Why do I need Arduino and connect the wires, I heard that one can reset Canon printer counters by just pressing some buttons on the printer or use the "Serivice Tool" software.
A: Those methods only works for old printers. As far as I know, for the new Canon printers with MC-G02, at the moment there is no such known easy methods. 

#### Q: What's the chip inside MC-G02
A: For the MC-G02 I got, it's labled as `416RT` by `STMicroelectronics`, which is acutally a `M24C16-R`, the datasheet can be found from the ST website[4].  Seems like there are also chips labeled as `G16` `4G16`, but the function of chip should be compatible with `416RT`.

#### Q: Does this project work for other cartridges?

Might work for other cartridges as well, without modification or small modification, as long as a similiar chip is used.

This project is confirmed (by user) to work with MC-G01 without any modification needed, see discussions [here](https://github.com/wangyu-/canon_mc-g02_resetter/issues/2).

## Reference

[1] https://microcontrollerslab.com/24c04-two-wire-serial-eeprom-interrfacing-arduino/

[2] https://www.youtube.com/watch?v=WZ5GESc6424&t=629s&ab_channel=SMtrainingacademy

[3] https://github.com/P-Find/arduino-24c16

[4] https://www.st.com/en/memories/m24c16-r.html