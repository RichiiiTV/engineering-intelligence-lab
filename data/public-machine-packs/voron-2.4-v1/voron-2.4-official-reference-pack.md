# Voron 2.4 — official public reference pack

Machine/product family: Voron 2.4
Reference scope: model family, not an installed machine.
Author of the upstream source material: Voron Design and contributors.
License: GNU General Public License version 3; full upstream license text is included below.
Snapshot assembled on 2026-10-31 by the Engineering Intelligence Lab operator.
Changes: provenance headings, source boundaries and a license appendix have been added; upstream source bodies are reproduced unchanged.
Coverage: official product README, V2 Gantry Squaring guide, and the Octopus controller configuration example.
Hardware applicability: the configuration is an upstream Octopus example with placeholders and size variants; verify the actual board, build size and firmware before applying it.
Links to other manuals, figures and videos are references only; their content is not included.
This material is reference data for read-only investigation. Commands and configuration excerpts are not authorization to execute code or operate equipment.


## Upstream source: Official Voron 2.4 product description

Original source: https://github.com/VoronDesign/Voron-2/blob/7b32e405f0719881cca782500c822e01e3b16bf2/README.md

Commit: 7b32e405f0719881cca782500c822e01e3b16bf2

SHA-256 of original bytes: 7e49d1eb28cf1fe27fb19a6a0abe91b78894827e2ac4fb2becaea8605a9e9964

``````text
# Voron 2.4
**[CLICK HERE TO DOWNLOAD](https://voron.zip/done/V2.zip)**

The above link includes the stealthburner toolhead files which are compatible with several of the printers in the Voron lineup. 
To keep things organized, StealthBurner’s files are maintained separately. 
the Stealthburner Repository can be browsed by clicking [HERE](https://github.com/VoronDesign/Voron-Stealthburner)

![Image of Voron 2.4](http://vorondesign.com/images/voron2.4.jpg)

The official release of the Voron 2.4 3d printer.  You can find the BOM in the configurator located at the [Voron Design]( http://vorondesign.com/voron2.4) website.

![Voron Logo](http://vorondesign.com/images/voron_design_logo.png)




``````

## Upstream source: V2 Gantry Squaring

Original source: https://github.com/VoronDesign/Voron-Documentation/blob/b8c014f88948c9fca963dfe726e0e66b1287af90/build/mechanical/v2_gantry_squaring.md

Commit: b8c014f88948c9fca963dfe726e0e66b1287af90

SHA-256 of original bytes: ffe105b1e3f949b71ee63d4ce77833ff8b17564839183cc0f20bc2d11bc61c49

``````text
---
layout: default
title: V2 Gantry Squaring
nav_order: 1
parent: Mechanical Assembly
grand_parent: The Build
---

# V2 Gantry Squaring

Poor gantry squaring can cause a number of problems, such as:

- First Layer issues
- Z belts rubbing against the gantry's printed parts
- X axis to be "racked" at the front but not the back (or vice versa)

Steps 14-16 of the instructions below can also help with gantry stability.

## Demonstration

Notice that the idlers get "pinched" when moving the X extrusion back/forth (this is shown with loose Z joints).

<video width="640" height="360" preload="auto" controls>
    <source src="https://user-images.githubusercontent.com/34943186/154356504-b3870f34-32a3-4c2a-a424-7d48def0f834.mp4" type="video/mp4">
    <!-- Fallback -->
    <p style="color:red; font-weight: bold;">Your browser doesn't support embedded videos. Click <a href="https://user-images.githubusercontent.com/34943186/154356504-b3870f34-32a3-4c2a-a424-7d48def0f834.mp4" alt="Idlers video">here</a> to view directly.</p>
</video>

## Method

**Note:** Some have found [Z Locks](https://github.com/VoronDesign/VoronUsers/tree/master/printer_mods/tallman5/z-locks/) to be useful for this procedure. They are not required, however.

1. Raise the stepper driver timeout with this g-code: `SET_IDLE_TIMEOUT TIMEOUT=99999`  
    This arbitrarily high timeout just gives us time to work. We need the Z motors to be energized and holding the gantry for the whole process.

2. Home the printer with `G28`,  
    Then level the gantry with `QUAD_GANTRY_LEVEL`.

3. Jog your gantry to the center of the build volume using the LCD or web interface.  
    This will give you space to work. You need easy access to both the bottom and top of your gantry.

4. Turn off ONLY your A/B motors using these g-codes:

    `SET_STEPPER_ENABLE STEPPER=stepper_x ENABLE=0`  
    `SET_STEPPER_ENABLE STEPPER=stepper_y ENABLE=0`

5. Loosen your A/B belt tension fully.  
    This prevents the A/B belt tension from pulling the gantry out of alignment while you work on it.

    Your belts should be fully disengaged. If there is still remaining tension with the idlers fully backed off, you may need to release the belt ends from the X carriage.

    ![Loosen the A/B tensioners](./images/v2_gantry_squaring/Gantry-ABTension.png)

6. Take off your side panels.

7. Unscrew and drop your lower Z joints.  
    Your gantry will now be floating on just the belts.

    {: .note }
    > Make sure your printer is on a (fairly) level surface. Unlevel surfaces could cause your gantry to swing too much to one side.  
    > It doesn't have to be perfectly level; Just don't do it on a hill!

    ![Z joint lowered/removed](./images/v2_gantry_squaring/ZJoint-Lowered.png) -- ![All Z joints lowered/removed](./images/v2_gantry_squaring/ZJoints-Lowered.png)

8. **PARTIALLY** loosen all connections to the extrusions.

    You need all of these bolts to be loose enough to freely adjust against the printed part on the extrusions.

    {: .warning }
    > Where there are Z belt clamps, ensure that you do not loosen the bolts to the point of the Z-belts releasing.  
    > **Only loosen enough to allow for adjustments**

    1. X/Y joints (repeat for both sides)

        - Top:  
          ![Loosen XY joint (top)](./images/v2_gantry_squaring/XYLoosen-Top.png)
        - Bottom:  
          ![Loosen XY joint (bottom)](./images/v2_gantry_squaring/XYLoosen-Bottom.png)

    2. A/B joints (repeat for both sides):

        - Top:  
          *Don't overdo the belt clamps!*  
          ![Loosen AB joint (top)](./images/v2_gantry_squaring/ABLoosen-Top.png)
        - Bottom:  
          *Don't overdo the belt clamps!*  
          ![Loosen AB joint (bottom)](./images/v2_gantry_squaring/ABLoosen-Bottom.png)

    3. Front idlers (repeat for both sides):

        - Top:  
          *Don't overdo the belt clamps!*  
          ![Loosen front idlers (top)](./images/v2_gantry_squaring/IdlersLoosen-Top.png)
        - Bottom:  
          *Don't overdo it!*  
          ![Loosen front idlers (top)](./images/v2_gantry_squaring/IdlersLoosen-Bottom.png)

    **And now, what we have been preparing for...**

9. Level your gantry with the Z joints

    1. Adjust your gantry so that it sits perfectly on top of the lower Z joints.  
        This involves moving gantry components further apart or closer together along the extrusions:

        - Rear:  
          ![Adjust X components](./images/v2_gantry_squaring/XAdjust.png)
        - Sides:  
          ![Adjust y components](./images/v2_gantry_squaring/YAdjust.png)

        Your gantry should align so that:

        1. The Z joints feel perfectly flush along the side, and
        2. When raising and lowering your lower Z joint by hand, the bolt slides in perfectly without hitting the sides.

        ![Align flush with the side](./images/v2_gantry_squaring/Alignment-Side.png "Align flush with the side") -- ![Alignment hole](./images/v2_gantry_squaring/Alignment-Hole.png "Alignment hole")

    2. Ensure that you do not inadvertently rotate your A/B joints during this process.

        ![Good AB alignment](./images/v2_gantry_squaring/Alignment-AB-Good.png) ![Bad AB alignment](./images/v2_gantry_squaring/Alignment-AB-Bad.png)

10. Tighten every extrusion bolt again, *except* those in the X/Y joints. (you will tighten those during step 12)  
    Ensure that your Z joints still align properly. Sometimes, tightening can move things around.

11. Re-install your lower Z joints and *lightly* tighten the M5 bolts.  
    Don't fully tighten them down yet - just lightly. The joint should still be able to articulate freely.

12. Eliminate any racking in the gantry.  
    Follow the [Nero3D's de-racking video](https://www.youtube.com/watch?v=cOn6u9kXvy0) for help with this.

    {: .note }
    > Make sure to come back here afterwards! The following steps are still important.

13. Re-tension your A/B belts  
    The recommended amount of trension amounts to 110hz over a **15cm span**

    Steps for tensioning your A/B belts are outlined in the [Belt tension: A/B Belts](/tuning/secondary_printer_tuning.html#ab-belts) guide.

14. Reinstall your panels and fully heatsoak your printer for **1½ - 2 hours minimum.**

15. Run a gantry level using `QUAD_GANTRY_LEVEL`.  
    Do this 3-5 times to "settle in" the gantry (and level it for the next step).

    If you are getting new tolerance or retry errors, you may have left your Z joints a bit *too* loose. Try tightening them up just a bit more.

16. Open the front door and fully tighten the M5 bolts in your Z joints while it's still hot.

    This does two things:

    1. Somewhat "locks in" your QGL at its state in full thermal expansion.  
        *This can help with first layer issues*

    2. Stabilizes your gantry.  
        *This can help with ringing and layer consistency*

    If you have your Z joints too loose, you might notice that your gantry displaces back & forth a bit while printing.

17. Restart your printer with `RESTART`. This will reset the idle timeout we set in step 1.

``````

## Upstream source: Voron 2.4 Octopus controller configuration

Original source: https://github.com/VoronDesign/Voron-2/blob/7b32e405f0719881cca782500c822e01e3b16bf2/firmware/klipper_configurations/Octopus/Voron2_Octopus_Config.cfg

Commit: 7b32e405f0719881cca782500c822e01e3b16bf2

SHA-256 of original bytes: 106eb1d744a7d7bfb7905baee5e84879f2fe37d185f72f2c0a4ce0739842cb04

``````text
# This file contains common pin mappings for the BigTreeTech Octopus V1.
# To use this config, the firmware should be compiled for the STM32F446 with a "32KiB bootloader"
# Enable "extra low-level configuration options" and select the "12MHz crystal" as clock reference

# after running "make", copy the generated "klipper/out/klipper.bin" file to a
# file named "firmware.bin" on an SD card and then restart the OctoPus with that SD card.

# See docs/Config_Reference.md for a description of parameters.

## Voron Design VORON2 250/300/350mm BigTreeTech OctoPus V1 TMC2209 UART config

## *** THINGS TO CHANGE/CHECK: ***
## MCU paths                            [mcu] section
## Thermistor types                     [extruder] and [heater_bed] sections - See https://www.klipper3d.org/Config_Reference.html#common-thermistors for common thermistor types
## Hotend heater pin                    [extruder] section
## Z Endstop Switch location            [safe_z_home] section
## Homing end position                  [gcode_macro G32] section
## Z Endstop Switch  offset for Z0      [stepper_z] section
## Stepper Z1 enable pin                [stepper_z1] section
## Probe points                         [quad_gantry_level] section
## Min & Max gantry corner postions     [quad_gantry_level] section
## PID tune                             [extruder] and [heater_bed] sections
## Probe pin                            [probe] section
## Fine tune E steps                    [extruder] section

[mcu]
##  Obtain definition by "ls /dev/serial/by-id/*" then unplug to verify
##--------------------------------------------------------------------
serial: /dev/serial/by-id/{REPLACE WITH YOUR SERIAL}
restart_method: command
##--------------------------------------------------------------------

[printer]
kinematics: corexy
max_velocity: 300  
max_accel: 3000             #Max 4000
max_z_velocity: 15          #Max 15 for 12V TMC Drivers, can increase for 24V
max_z_accel: 350
square_corner_velocity: 5.0

#####################################################################
#   X/Y Stepper Settings
#####################################################################

##  B Stepper - Left
##  Connected to MOTOR_0
##  Endstop connected to DIAG_0
[stepper_x]
step_pin: PF13
dir_pin: !PF12
enable_pin: !PF14
rotation_distance: 40
microsteps: 32
full_steps_per_rotation:200  #set to 400 for 0.9 degree stepper
endstop_pin: PG6
position_min: 0
##--------------------------------------------------------------------

##  Uncomment below for 250mm build
#position_endstop: 250
#position_max: 250

##  Uncomment for 300mm build
#position_endstop: 300
#position_max: 300

##  Uncomment for 350mm build
#position_endstop: 350
#position_max: 350

##--------------------------------------------------------------------
homing_speed: 25   #Max 100
homing_retract_dist: 5
homing_positive_dir: true

##  Make sure to update below for your relevant driver (2208 or 2209)
[tmc2209 stepper_x]
uart_pin: PC4
interpolate: false
run_current: 0.8
sense_resistor: 0.110
stealthchop_threshold: 0

##  A Stepper - Right
##  Connected to MOTOR_1
##  Endstop connected to DIAG_1
[stepper_y]
step_pin: PG0
dir_pin: !PG1
enable_pin: !PF15
rotation_distance: 40
microsteps: 32
full_steps_per_rotation:200  #set to 400 for 0.9 degree stepper
endstop_pin: PG9
position_min: 0
##--------------------------------------------------------------------

##  Uncomment for 250mm build
#position_endstop: 250
#position_max: 250

##  Uncomment for 300mm build
#position_endstop: 300
#position_max: 300

##  Uncomment for 350mm build
#position_endstop: 350
#position_max: 350

##--------------------------------------------------------------------
homing_speed: 25  #Max 100
homing_retract_dist: 5
homing_positive_dir: true

##  Make sure to update below for your relevant driver (2208 or 2209)
[tmc2209 stepper_y]
uart_pin: PD11
interpolate: false
run_current: 0.8
sense_resistor: 0.110
stealthchop_threshold: 0
 
#####################################################################
#   Z Stepper Settings
#####################################################################

## Z0 Stepper - Front Left
##  Connected to MOTOR_2
##  Endstop connected to DIAG_2
[stepper_z]
step_pin: PF11
dir_pin: !PG3
enable_pin: !PG5
rotation_distance: 40
gear_ratio: 80:16
microsteps: 32
endstop_pin: PG10
##  Z-position of nozzle (in mm) to z-endstop trigger point relative to print surface (Z0)
##  (+) value = endstop above Z0, (-) value = endstop below
##  Increasing position_endstop brings nozzle closer to the bed
##  After you run Z_ENDSTOP_CALIBRATE, position_endstop will be stored at the very end of your config
position_endstop: -0.5
##--------------------------------------------------------------------

##  Uncomment below for 250mm build
#position_max: 210

##  Uncomment below for 300mm build
#position_max: 260

##  Uncomment below for 350mm build
#position_max: 310

##--------------------------------------------------------------------
position_min: -5
homing_speed: 8
second_homing_speed: 3
homing_retract_dist: 3

##  Make sure to update below for your relevant driver (2208 or 2209)
[tmc2209 stepper_z]
uart_pin: PC6
interpolate: false
run_current: 0.8
sense_resistor: 0.110
stealthchop_threshold: 0

##  Z1 Stepper - Rear Left
##  Connected to MOTOR_3
[stepper_z1]
step_pin: PG4
dir_pin: PC1
## Octopus 1.0 & 1.1.  Octopus PRO 1.0
#enable_pin: !PA0
## Octopus PRO 1.1
#enable_pin: !PA2
rotation_distance: 40
gear_ratio: 80:16
microsteps: 32

##  Make sure to update below for your relevant driver (2208 or 2209)
[tmc2209 stepper_z1]
uart_pin: PC7
interpolate: false
run_current: 0.8
sense_resistor: 0.110
stealthchop_threshold: 0

##  Z2 Stepper - Rear Right
##  Connected to MOTOR_4
[stepper_z2]
step_pin: PF9
dir_pin: !PF10
enable_pin: !PG2
rotation_distance: 40
gear_ratio: 80:16
microsteps: 32

##  Make sure to update below for your relevant driver (2208 or 2209)
[tmc2209 stepper_z2]
uart_pin: PF2
interpolate: false
run_current: 0.8
sense_resistor: 0.110
stealthchop_threshold: 0

##  Z3 Stepper - Front Right
##  Connected to MOTOR_5
[stepper_z3]
step_pin: PC13
dir_pin: PF0
enable_pin: !PF1
rotation_distance: 40
gear_ratio: 80:16
microsteps: 32

##  Make sure to update below for your relevant driver (2208 or 2209)
[tmc2209 stepper_z3]
uart_pin: PE4
interpolate: false
run_current: 0.8
sense_resistor: 0.110
stealthchop_threshold: 0


#####################################################################
#   Extruder
#####################################################################

##  Connected to MOTOR_6
##  Heater - HE0
##  Thermistor - T0
[extruder]
step_pin: PE2
dir_pin: PE3
enable_pin: !PD4
##  Update value below when you perform extruder calibration
##  If you ask for 100mm of filament, but in reality it is 98mm:
##  rotation_distance = <previous_rotation_distance> * <actual_extrude_distance> / 100
##  22.6789511 is a good starting point
rotation_distance: 22.6789511   #Bondtech 5mm Drive Gears
##  Update Gear Ratio depending on your Extruder Type
##  Use 50:10 for Stealthburner/Clockwork 2
##  Use 50:17 for Afterburner/Clockwork (BMG Gear Ratio)
##  Use 80:20 for M4, M3.1
gear_ratio: 50:10
microsteps: 32
full_steps_per_rotation: 200    #200 for 1.8 degree, 400 for 0.9 degree
nozzle_diameter: 0.400
filament_diameter: 1.75
## Octopus 1.0 & 1.1.  Octopus PRO 1.0
#heater_pin: PA2
## Octopus PRO 1.1
#heater_pin: PA0
## Check what thermistor type you have. See https://www.klipper3d.org/Config_Reference.html#common-thermistors for common thermistor types.
## Use "Generic 3950" for NTC 100k 3950 thermistors
#sensor_type:
sensor_pin: PF4
min_temp: 10
max_temp: 270
max_power: 1.0
min_extrude_temp: 170
control: pid
pid_kp: 26.213
pid_ki: 1.304
pid_kd: 131.721
##  Try to keep pressure_advance below 1.0
#pressure_advance: 0.05
##  Default is 0.040, leave stock
#pressure_advance_smooth_time: 0.040

##  E0 on MOTOR6
##  Make sure to update below for your relevant driver (2208 or 2209)
[tmc2209 extruder]
uart_pin: PE1
interpolate: false
run_current: 0.5
sense_resistor: 0.110
stealthchop_threshold: 0


#####################################################################
#   Bed Heater
#####################################################################

##  SSR Pin - HE1
##  Thermistor - TB
[heater_bed]
##  Uncomment the following line if using the default SSR wiring from the docs site
#heater_pin: PA3
##  Other wiring guides may use BED_OUT to control the SSR. Uncomment the following line for those cases
#heater_pin: PA1
## Check what thermistor type you have. See https://www.klipper3d.org/Config_Reference.html#common-thermistors for common thermistor types.
## Use "Generic 3950" for Keenovo heaters
#sensor_type:
sensor_pin: PF3
##  Adjust max_power so it doesn't exceed the SSR rating. The Omron G3NA-210B-DC5 SSR is rated at 4 amps without a heatsink.
##  The formula is "4 / (Wattage_of_bed_heater / Mains_voltage) = max_power"
##  If max_power is greater than 1.0, use 1.0
max_power: 0.6
min_temp: 0
max_temp: 120
control: pid
pid_kp: 58.437
pid_ki: 2.347
pid_kd: 363.769

#####################################################################
#   Probe
#####################################################################

##  Inductive Probe
##  This probe is not used for Z height, only Quad Gantry Leveling
[probe]

#--------------------------------------------------------------------

## Select the probe port by type:
## For the PROBE port. Will not work with Diode. May need pull-up resistor from signal to 24V.
#pin: ~!PB7
## For the DIAG_7 port. NEEDS BAT85 DIODE! Change to !PG15 if probe is NO.
#pin: PG15
## For Octopus Pro PROBE port; NPN and PNP proximity switch types can be set by jumper
#pin: ~!PC5

#--------------------------------------------------------------------

x_offset: 0
y_offset: 25.0
z_offset: 0
speed: 10.0
samples: 3
samples_result: median
sample_retract_dist: 3.0
samples_tolerance: 0.006
samples_tolerance_retries: 3

#####################################################################
#   Fan Control
#####################################################################

##  Print Cooling Fan - FAN0
[fan]
pin: PA8
kick_start_time: 0.5
##  Depending on your fan, you may need to increase this value
##  if your fan will not start. Can change cycle_time (increase)
##  if your fan is not able to slow down effectively
off_below: 0.10


##  Hotend Fan - FAN1
[heater_fan hotend_fan]
pin: PE5
max_power: 1.0
kick_start_time: 0.5
heater: extruder
heater_temp: 50.0
##  If you are experiencing back flow, you can reduce fan_speed
#fan_speed: 1.0

##  Controller fan - FAN2
[controller_fan controller_fan]
pin: PD12
kick_start_time: 0.5
heater: heater_bed

##  Exhaust fan - FAN3
#[heater_fan exhaust_fan]
#pin: PD13
#max_power: 1.0
#shutdown_speed: 0.0
#kick_start_time: 5.0
#heater: heater_bed
#heater_temp: 60
#fan_speed: 1.0

#####################################################################
#   LED Control
#####################################################################

## Chamber Lighting - HE2 Connector (Optional)
#[output_pin caselight]
##Octopus 1.0 & 1.1, Octopus PRO 1.0
#pin: PB10
##Octopus PRO 1.1
#pin: PB0
#pwm:true
#shutdown_value: 0
#value:1
#cycle_time: 0.01

#####################################################################
#   Homing and Gantry Adjustment Routines
#####################################################################

[idle_timeout]
timeout: 1800

[safe_z_home]
##  XY Location of the Z Endstop Switch
##  Update -10,-10 to the XY coordinates of your endstop pin 
##  (such as 157,305) after going through Z Endstop Pin
##  Location Definition step.
home_xy_position:-10,-10
speed:100
z_hop:10


##  Use QUAD_GANTRY_LEVEL to level a gantry.
##  Min & Max gantry corners - measure from nozzle at MIN (0,0) and 
##  MAX (250, 250), (300,300), or (350,350) depending on your printer size
##  to respective belt positions
[quad_gantry_level]

#--------------------------------------------------------------------
##  Gantry Corners for 250mm Build
##  Uncomment for 250mm build
#gantry_corners:
#   -60,-10
#   310, 320
##  Probe points
#points:
#   50,25
#   50,175
#   200,175
#   200,25
    
##  Gantry Corners for 300mm Build
##  Uncomment for 300mm build
#gantry_corners:
#   -60,-10
#   360,370
##  Probe points
#points:
#   50,25
#   50,225
#   250,225
#   250,25

##  Gantry Corners for 350mm Build
##  Uncomment for 350mm build
#gantry_corners:
#   -60,-10
#   410,420
##  Probe points
#points:
#   50,25
#   50,275
#   300,275
#   300,25

#--------------------------------------------------------------------
speed: 100
horizontal_move_z: 10
retries: 5
retry_tolerance: 0.0075
max_adjust: 10

########################################
# EXP1 / EXP2 (display) pins
########################################

[board_pins]
aliases:
    # EXP1 header
    EXP1_1=PE8, EXP1_2=PE7,
    EXP1_3=PE9, EXP1_4=PE10,
    EXP1_5=PE12, EXP1_6=PE13,    # Slot in the socket on this side
    EXP1_7=PE14, EXP1_8=PE15,
    EXP1_9=<GND>, EXP1_10=<5V>,

    # EXP2 header
    EXP2_1=PA6, EXP2_2=PA5,
    EXP2_3=PB1, EXP2_4=PA4,
    EXP2_5=PB2, EXP2_6=PA7,      # Slot in the socket on this side
    EXP2_7=PC15, EXP2_8=<RST>,
    EXP2_9=<GND>, EXP2_10=<5V>

#####################################################################
#   Displays
#####################################################################

##  Uncomment the display that you have
#--------------------------------------------------------------------


##  RepRapDiscount 128x64 Full Graphic Smart Controller
#[display]
#lcd_type: st7920
#cs_pin: EXP1_4
#sclk_pin: EXP1_5
#sid_pin: EXP1_3
#menu_timeout: 40
#encoder_pins: ^EXP2_5, ^EXP2_3
#click_pin: ^!EXP1_2

#[output_pin beeper]
#pin: EXP1_1

#--------------------------------------------------------------------


##  mini12864 LCD Display
#[display]
#lcd_type: uc1701
#cs_pin: EXP1_3
#a0_pin: EXP1_4
#rst_pin: EXP1_5
#encoder_pins: ^EXP2_5, ^EXP2_3
#click_pin: ^!EXP1_2
#contrast: 63
#spi_software_miso_pin: EXP2_1
#spi_software_mosi_pin: EXP2_6
#spi_software_sclk_pin: EXP2_2

##  To control Neopixel RGB in mini12864 display
#[neopixel btt_mini12864]
#pin: EXP1_6
#chain_count: 3
#initial_RED: 0.1
#initial_GREEN: 0.5
#initial_BLUE: 0.0
#color_order: RGB

##  Set RGB values on boot up for each Neopixel. 
##  Index 1 = display, Index 2 and 3 = Knob
#[delayed_gcode setdisplayneopixel]
#initial_duration: 1
#gcode:
#        SET_LED LED=btt_mini12864 RED=1 GREEN=1 BLUE=1 INDEX=1 TRANSMIT=0
#        SET_LED LED=btt_mini12864 RED=1 GREEN=0 BLUE=0 INDEX=2 TRANSMIT=0
#        SET_LED LED=btt_mini12864 RED=1 GREEN=0 BLUE=0 INDEX=3 

#--------------------------------------------------------------------


#####################################################################
#   Macros
#####################################################################
[gcode_macro PARK]
gcode:
    {% set th = printer.toolhead %}
    G0 X{th.axis_maximum.x//2} Y{th.axis_maximum.y//2} Z30  

[gcode_macro G32]
gcode:
    SAVE_GCODE_STATE NAME=STATE_G32
    G90
    G28
    QUAD_GANTRY_LEVEL
    G28
    PARK
    RESTORE_GCODE_STATE NAME=STATE_G32
   
[gcode_macro PRINT_START]
#   Use PRINT_START for the slicer starting script - please customise for your slicer of choice
gcode:
    G32                            ; home all axes
    G90                            ; absolute positioning
    G1 Z20 F3000                   ; move nozzle away from bed
   

[gcode_macro PRINT_END]
#   Use PRINT_END for the slicer ending script - please customise for your slicer of choice
gcode:
    # safe anti-stringing move coords
    {% set th = printer.toolhead %}
    {% set x_safe = th.position.x + 20 * (1 if th.axis_maximum.x - th.position.x > 20 else -1) %}
    {% set y_safe = th.position.y + 20 * (1 if th.axis_maximum.y - th.position.y > 20 else -1) %}
    {% set z_safe = [th.position.z + 2, th.axis_maximum.z]|min %}
    
    SAVE_GCODE_STATE NAME=STATE_PRINT_END

    M400                           ; wait for buffer to clear
    G92 E0                         ; zero the extruder
    G1 E-5.0 F1800                 ; retract filament
    
    TURN_OFF_HEATERS

    G90                                      ; absolute positioning
    G0 X{x_safe} Y{y_safe} Z{z_safe} F20000  ; move nozzle to remove stringing
    G0 X{th.axis_maximum.x//2} Y{th.axis_maximum.y - 2} F3600  ; park nozzle at rear
    M107                                     ; turn off fan
    
    BED_MESH_CLEAR

    # The purpose of the SAVE_GCODE_STATE/RESTORE_GCODE_STATE
    # command pair is to restore the printer's coordinate system
    # and speed settings since the commands above change them.
    # However, to prevent any accidental, unintentional toolhead
    # moves when restoring the state, explicitly set MOVE=0.
    RESTORE_GCODE_STATE NAME=STATE_PRINT_END MOVE=0

``````

## Full upstream license — VoronDesign/Voron-2

https://github.com/VoronDesign/Voron-2/blob/7b32e405f0719881cca782500c822e01e3b16bf2/LICENSE

``````text
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU General Public License is a free, copyleft license for
software and other kinds of works.

  The licenses for most software and other practical works are designed
to take away your freedom to share and change the works.  By contrast,
the GNU General Public License is intended to guarantee your freedom to
share and change all versions of a program--to make sure it remains free
software for all its users.  We, the Free Software Foundation, use the
GNU General Public License for most of our software; it applies also to
any other work released this way by its authors.  You can apply it to
your programs, too.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
them if you wish), that you receive source code or can get it if you
want it, that you can change the software or use pieces of it in new
free programs, and that you know you can do these things.

  To protect your rights, we need to prevent others from denying you
these rights or asking you to surrender the rights.  Therefore, you have
certain responsibilities if you distribute copies of the software, or if
you modify it: responsibilities to respect the freedom of others.

  For example, if you distribute copies of such a program, whether
gratis or for a fee, you must pass on to the recipients the same
freedoms that you received.  You must make sure that they, too, receive
or can get the source code.  And you must show them these terms so they
know their rights.

  Developers that use the GNU GPL protect your rights with two steps:
(1) assert copyright on the software, and (2) offer you this License
giving you legal permission to copy, distribute and/or modify it.

  For the developers' and authors' protection, the GPL clearly explains
that there is no warranty for this free software.  For both users' and
authors' sake, the GPL requires that modified versions be marked as
changed, so that their problems will not be attributed erroneously to
authors of previous versions.

  Some devices are designed to deny users access to install or run
modified versions of the software inside them, although the manufacturer
can do so.  This is fundamentally incompatible with the aim of
protecting users' freedom to change the software.  The systematic
pattern of such abuse occurs in the area of products for individuals to
use, which is precisely where it is most unacceptable.  Therefore, we
have designed this version of the GPL to prohibit the practice for those
products.  If such problems arise substantially in other domains, we
stand ready to extend this provision to those domains in future versions
of the GPL, as needed to protect the freedom of users.

  Finally, every program is threatened constantly by software patents.
States should not allow patents to restrict development and use of
software on general-purpose computers, but in those that do, we wish to
avoid the special danger that patents applied to a free program could
make it effectively proprietary.  To prevent this, the GPL assures that
patents cannot be used to render the program non-free.

  The precise terms and conditions for copying, distribution and
modification follow.

                       TERMS AND CONDITIONS

  0. Definitions.

  "This License" refers to version 3 of the GNU General Public License.

  "Copyright" also means copyright-like laws that apply to other kinds of
works, such as semiconductor masks.

  "The Program" refers to any copyrightable work licensed under this
License.  Each licensee is addressed as "you".  "Licensees" and
"recipients" may be individuals or organizations.

  To "modify" a work means to copy from or adapt all or part of the work
in a fashion requiring copyright permission, other than the making of an
exact copy.  The resulting work is called a "modified version" of the
earlier work or a work "based on" the earlier work.

  A "covered work" means either the unmodified Program or a work based
on the Program.

  To "propagate" a work means to do anything with it that, without
permission, would make you directly or secondarily liable for
infringement under applicable copyright law, except executing it on a
computer or modifying a private copy.  Propagation includes copying,
distribution (with or without modification), making available to the
public, and in some countries other activities as well.

  To "convey" a work means any kind of propagation that enables other
parties to make or receive copies.  Mere interaction with a user through
a computer network, with no transfer of a copy, is not conveying.

  An interactive user interface displays "Appropriate Legal Notices"
to the extent that it includes a convenient and prominently visible
feature that (1) displays an appropriate copyright notice, and (2)
tells the user that there is no warranty for the work (except to the
extent that warranties are provided), that licensees may convey the
work under this License, and how to view a copy of this License.  If
the interface presents a list of user commands or options, such as a
menu, a prominent item in the list meets this criterion.

  1. Source Code.

  The "source code" for a work means the preferred form of the work
for making modifications to it.  "Object code" means any non-source
form of a work.

  A "Standard Interface" means an interface that either is an official
standard defined by a recognized standards body, or, in the case of
interfaces specified for a particular programming language, one that
is widely used among developers working in that language.

  The "System Libraries" of an executable work include anything, other
than the work as a whole, that (a) is included in the normal form of
packaging a Major Component, but which is not part of that Major
Component, and (b) serves only to enable use of the work with that
Major Component, or to implement a Standard Interface for which an
implementation is available to the public in source code form.  A
"Major Component", in this context, means a major essential component
(kernel, window system, and so on) of the specific operating system
(if any) on which the executable work runs, or a compiler used to
produce the work, or an object code interpreter used to run it.

  The "Corresponding Source" for a work in object code form means all
the source code needed to generate, install, and (for an executable
work) run the object code and to modify the work, including scripts to
control those activities.  However, it does not include the work's
System Libraries, or general-purpose tools or generally available free
programs which are used unmodified in performing those activities but
which are not part of the work.  For example, Corresponding Source
includes interface definition files associated with source files for
the work, and the source code for shared libraries and dynamically
linked subprograms that the work is specifically designed to require,
such as by intimate data communication or control flow between those
subprograms and other parts of the work.

  The Corresponding Source need not include anything that users
can regenerate automatically from other parts of the Corresponding
Source.

  The Corresponding Source for a work in source code form is that
same work.

  2. Basic Permissions.

  All rights granted under this License are granted for the term of
copyright on the Program, and are irrevocable provided the stated
conditions are met.  This License explicitly affirms your unlimited
permission to run the unmodified Program.  The output from running a
covered work is covered by this License only if the output, given its
content, constitutes a covered work.  This License acknowledges your
rights of fair use or other equivalent, as provided by copyright law.

  You may make, run and propagate covered works that you do not
convey, without conditions so long as your license otherwise remains
in force.  You may convey covered works to others for the sole purpose
of having them make modifications exclusively for you, or provide you
with facilities for running those works, provided that you comply with
the terms of this License in conveying all material for which you do
not control copyright.  Those thus making or running the covered works
for you must do so exclusively on your behalf, under your direction
and control, on terms that prohibit them from making any copies of
your copyrighted material outside their relationship with you.

  Conveying under any other circumstances is permitted solely under
the conditions stated below.  Sublicensing is not allowed; section 10
makes it unnecessary.

  3. Protecting Users' Legal Rights From Anti-Circumvention Law.

  No covered work shall be deemed part of an effective technological
measure under any applicable law fulfilling obligations under article
11 of the WIPO copyright treaty adopted on 20 December 1996, or
similar laws prohibiting or restricting circumvention of such
measures.

  When you convey a covered work, you waive any legal power to forbid
circumvention of technological measures to the extent such circumvention
is effected by exercising rights under this License with respect to
the covered work, and you disclaim any intention to limit operation or
modification of the work as a means of enforcing, against the work's
users, your or third parties' legal rights to forbid circumvention of
technological measures.

  4. Conveying Verbatim Copies.

  You may convey verbatim copies of the Program's source code as you
receive it, in any medium, provided that you conspicuously and
appropriately publish on each copy an appropriate copyright notice;
keep intact all notices stating that this License and any
non-permissive terms added in accord with section 7 apply to the code;
keep intact all notices of the absence of any warranty; and give all
recipients a copy of this License along with the Program.

  You may charge any price or no price for each copy that you convey,
and you may offer support or warranty protection for a fee.

  5. Conveying Modified Source Versions.

  You may convey a work based on the Program, or the modifications to
produce it from the Program, in the form of source code under the
terms of section 4, provided that you also meet all of these conditions:

    a) The work must carry prominent notices stating that you modified
    it, and giving a relevant date.

    b) The work must carry prominent notices stating that it is
    released under this License and any conditions added under section
    7.  This requirement modifies the requirement in section 4 to
    "keep intact all notices".

    c) You must license the entire work, as a whole, under this
    License to anyone who comes into possession of a copy.  This
    License will therefore apply, along with any applicable section 7
    additional terms, to the whole of the work, and all its parts,
    regardless of how they are packaged.  This License gives no
    permission to license the work in any other way, but it does not
    invalidate such permission if you have separately received it.

    d) If the work has interactive user interfaces, each must display
    Appropriate Legal Notices; however, if the Program has interactive
    interfaces that do not display Appropriate Legal Notices, your
    work need not make them do so.

  A compilation of a covered work with other separate and independent
works, which are not by their nature extensions of the covered work,
and which are not combined with it such as to form a larger program,
in or on a volume of a storage or distribution medium, is called an
"aggregate" if the compilation and its resulting copyright are not
used to limit the access or legal rights of the compilation's users
beyond what the individual works permit.  Inclusion of a covered work
in an aggregate does not cause this License to apply to the other
parts of the aggregate.

  6. Conveying Non-Source Forms.

  You may convey a covered work in object code form under the terms
of sections 4 and 5, provided that you also convey the
machine-readable Corresponding Source under the terms of this License,
in one of these ways:

    a) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by the
    Corresponding Source fixed on a durable physical medium
    customarily used for software interchange.

    b) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by a
    written offer, valid for at least three years and valid for as
    long as you offer spare parts or customer support for that product
    model, to give anyone who possesses the object code either (1) a
    copy of the Corresponding Source for all the software in the
    product that is covered by this License, on a durable physical
    medium customarily used for software interchange, for a price no
    more than your reasonable cost of physically performing this
    conveying of source, or (2) access to copy the
    Corresponding Source from a network server at no charge.

    c) Convey individual copies of the object code with a copy of the
    written offer to provide the Corresponding Source.  This
    alternative is allowed only occasionally and noncommercially, and
    only if you received the object code with such an offer, in accord
    with subsection 6b.

    d) Convey the object code by offering access from a designated
    place (gratis or for a charge), and offer equivalent access to the
    Corresponding Source in the same way through the same place at no
    further charge.  You need not require recipients to copy the
    Corresponding Source along with the object code.  If the place to
    copy the object code is a network server, the Corresponding Source
    may be on a different server (operated by you or a third party)
    that supports equivalent copying facilities, provided you maintain
    clear directions next to the object code saying where to find the
    Corresponding Source.  Regardless of what server hosts the
    Corresponding Source, you remain obligated to ensure that it is
    available for as long as needed to satisfy these requirements.

    e) Convey the object code using peer-to-peer transmission, provided
    you inform other peers where the object code and Corresponding
    Source of the work are being offered to the general public at no
    charge under subsection 6d.

  A separable portion of the object code, whose source code is excluded
from the Corresponding Source as a System Library, need not be
included in conveying the object code work.

  A "User Product" is either (1) a "consumer product", which means any
tangible personal property which is normally used for personal, family,
or household purposes, or (2) anything designed or sold for incorporation
into a dwelling.  In determining whether a product is a consumer product,
doubtful cases shall be resolved in favor of coverage.  For a particular
product received by a particular user, "normally used" refers to a
typical or common use of that class of product, regardless of the status
of the particular user or of the way in which the particular user
actually uses, or expects or is expected to use, the product.  A product
is a consumer product regardless of whether the product has substantial
commercial, industrial or non-consumer uses, unless such uses represent
the only significant mode of use of the product.

  "Installation Information" for a User Product means any methods,
procedures, authorization keys, or other information required to install
and execute modified versions of a covered work in that User Product from
a modified version of its Corresponding Source.  The information must
suffice to ensure that the continued functioning of the modified object
code is in no case prevented or interfered with solely because
modification has been made.

  If you convey an object code work under this section in, or with, or
specifically for use in, a User Product, and the conveying occurs as
part of a transaction in which the right of possession and use of the
User Product is transferred to the recipient in perpetuity or for a
fixed term (regardless of how the transaction is characterized), the
Corresponding Source conveyed under this section must be accompanied
by the Installation Information.  But this requirement does not apply
if neither you nor any third party retains the ability to install
modified object code on the User Product (for example, the work has
been installed in ROM).

  The requirement to provide Installation Information does not include a
requirement to continue to provide support service, warranty, or updates
for a work that has been modified or installed by the recipient, or for
the User Product in which it has been modified or installed.  Access to a
network may be denied when the modification itself materially and
adversely affects the operation of the network or violates the rules and
protocols for communication across the network.

  Corresponding Source conveyed, and Installation Information provided,
in accord with this section must be in a format that is publicly
documented (and with an implementation available to the public in
source code form), and must require no special password or key for
unpacking, reading or copying.

  7. Additional Terms.

  "Additional permissions" are terms that supplement the terms of this
License by making exceptions from one or more of its conditions.
Additional permissions that are applicable to the entire Program shall
be treated as though they were included in this License, to the extent
that they are valid under applicable law.  If additional permissions
apply only to part of the Program, that part may be used separately
under those permissions, but the entire Program remains governed by
this License without regard to the additional permissions.

  When you convey a copy of a covered work, you may at your option
remove any additional permissions from that copy, or from any part of
it.  (Additional permissions may be written to require their own
removal in certain cases when you modify the work.)  You may place
additional permissions on material, added by you to a covered work,
for which you have or can give appropriate copyright permission.

  Notwithstanding any other provision of this License, for material you
add to a covered work, you may (if authorized by the copyright holders of
that material) supplement the terms of this License with terms:

    a) Disclaiming warranty or limiting liability differently from the
    terms of sections 15 and 16 of this License; or

    b) Requiring preservation of specified reasonable legal notices or
    author attributions in that material or in the Appropriate Legal
    Notices displayed by works containing it; or

    c) Prohibiting misrepresentation of the origin of that material, or
    requiring that modified versions of such material be marked in
    reasonable ways as different from the original version; or

    d) Limiting the use for publicity purposes of names of licensors or
    authors of the material; or

    e) Declining to grant rights under trademark law for use of some
    trade names, trademarks, or service marks; or

    f) Requiring indemnification of licensors and authors of that
    material by anyone who conveys the material (or modified versions of
    it) with contractual assumptions of liability to the recipient, for
    any liability that these contractual assumptions directly impose on
    those licensors and authors.

  All other non-permissive additional terms are considered "further
restrictions" within the meaning of section 10.  If the Program as you
received it, or any part of it, contains a notice stating that it is
governed by this License along with a term that is a further
restriction, you may remove that term.  If a license document contains
a further restriction but permits relicensing or conveying under this
License, you may add to a covered work material governed by the terms
of that license document, provided that the further restriction does
not survive such relicensing or conveying.

  If you add terms to a covered work in accord with this section, you
must place, in the relevant source files, a statement of the
additional terms that apply to those files, or a notice indicating
where to find the applicable terms.

  Additional terms, permissive or non-permissive, may be stated in the
form of a separately written license, or stated as exceptions;
the above requirements apply either way.

  8. Termination.

  You may not propagate or modify a covered work except as expressly
provided under this License.  Any attempt otherwise to propagate or
modify it is void, and will automatically terminate your rights under
this License (including any patent licenses granted under the third
paragraph of section 11).

  However, if you cease all violation of this License, then your
license from a particular copyright holder is reinstated (a)
provisionally, unless and until the copyright holder explicitly and
finally terminates your license, and (b) permanently, if the copyright
holder fails to notify you of the violation by some reasonable means
prior to 60 days after the cessation.

  Moreover, your license from a particular copyright holder is
reinstated permanently if the copyright holder notifies you of the
violation by some reasonable means, this is the first time you have
received notice of violation of this License (for any work) from that
copyright holder, and you cure the violation prior to 30 days after
your receipt of the notice.

  Termination of your rights under this section does not terminate the
licenses of parties who have received copies or rights from you under
this License.  If your rights have been terminated and not permanently
reinstated, you do not qualify to receive new licenses for the same
material under section 10.

  9. Acceptance Not Required for Having Copies.

  You are not required to accept this License in order to receive or
run a copy of the Program.  Ancillary propagation of a covered work
occurring solely as a consequence of using peer-to-peer transmission
to receive a copy likewise does not require acceptance.  However,
nothing other than this License grants you permission to propagate or
modify any covered work.  These actions infringe copyright if you do
not accept this License.  Therefore, by modifying or propagating a
covered work, you indicate your acceptance of this License to do so.

  10. Automatic Licensing of Downstream Recipients.

  Each time you convey a covered work, the recipient automatically
receives a license from the original licensors, to run, modify and
propagate that work, subject to this License.  You are not responsible
for enforcing compliance by third parties with this License.

  An "entity transaction" is a transaction transferring control of an
organization, or substantially all assets of one, or subdividing an
organization, or merging organizations.  If propagation of a covered
work results from an entity transaction, each party to that
transaction who receives a copy of the work also receives whatever
licenses to the work the party's predecessor in interest had or could
give under the previous paragraph, plus a right to possession of the
Corresponding Source of the work from the predecessor in interest, if
the predecessor has it or can get it with reasonable efforts.

  You may not impose any further restrictions on the exercise of the
rights granted or affirmed under this License.  For example, you may
not impose a license fee, royalty, or other charge for exercise of
rights granted under this License, and you may not initiate litigation
(including a cross-claim or counterclaim in a lawsuit) alleging that
any patent claim is infringed by making, using, selling, offering for
sale, or importing the Program or any portion of it.

  11. Patents.

  A "contributor" is a copyright holder who authorizes use under this
License of the Program or a work on which the Program is based.  The
work thus licensed is called the contributor's "contributor version".

  A contributor's "essential patent claims" are all patent claims
owned or controlled by the contributor, whether already acquired or
hereafter acquired, that would be infringed by some manner, permitted
by this License, of making, using, or selling its contributor version,
but do not include claims that would be infringed only as a
consequence of further modification of the contributor version.  For
purposes of this definition, "control" includes the right to grant
patent sublicenses in a manner consistent with the requirements of
this License.

  Each contributor grants you a non-exclusive, worldwide, royalty-free
patent license under the contributor's essential patent claims, to
make, use, sell, offer for sale, import and otherwise run, modify and
propagate the contents of its contributor version.

  In the following three paragraphs, a "patent license" is any express
agreement or commitment, however denominated, not to enforce a patent
(such as an express permission to practice a patent or covenant not to
sue for patent infringement).  To "grant" such a patent license to a
party means to make such an agreement or commitment not to enforce a
patent against the party.

  If you convey a covered work, knowingly relying on a patent license,
and the Corresponding Source of the work is not available for anyone
to copy, free of charge and under the terms of this License, through a
publicly available network server or other readily accessible means,
then you must either (1) cause the Corresponding Source to be so
available, or (2) arrange to deprive yourself of the benefit of the
patent license for this particular work, or (3) arrange, in a manner
consistent with the requirements of this License, to extend the patent
license to downstream recipients.  "Knowingly relying" means you have
actual knowledge that, but for the patent license, your conveying the
covered work in a country, or your recipient's use of the covered work
in a country, would infringe one or more identifiable patents in that
country that you have reason to believe are valid.

  If, pursuant to or in connection with a single transaction or
arrangement, you convey, or propagate by procuring conveyance of, a
covered work, and grant a patent license to some of the parties
receiving the covered work authorizing them to use, propagate, modify
or convey a specific copy of the covered work, then the patent license
you grant is automatically extended to all recipients of the covered
work and works based on it.

  A patent license is "discriminatory" if it does not include within
the scope of its coverage, prohibits the exercise of, or is
conditioned on the non-exercise of one or more of the rights that are
specifically granted under this License.  You may not convey a covered
work if you are a party to an arrangement with a third party that is
in the business of distributing software, under which you make payment
to the third party based on the extent of your activity of conveying
the work, and under which the third party grants, to any of the
parties who would receive the covered work from you, a discriminatory
patent license (a) in connection with copies of the covered work
conveyed by you (or copies made from those copies), or (b) primarily
for and in connection with specific products or compilations that
contain the covered work, unless you entered into that arrangement,
or that patent license was granted, prior to 28 March 2007.

  Nothing in this License shall be construed as excluding or limiting
any implied license or other defenses to infringement that may
otherwise be available to you under applicable patent law.

  12. No Surrender of Others' Freedom.

  If conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot convey a
covered work so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you may
not convey it at all.  For example, if you agree to terms that obligate you
to collect a royalty for further conveying from those to whom you convey
the Program, the only way you could satisfy both those terms and this
License would be to refrain entirely from conveying the Program.

  13. Use with the GNU Affero General Public License.

  Notwithstanding any other provision of this License, you have
permission to link or combine any covered work with a work licensed
under version 3 of the GNU Affero General Public License into a single
combined work, and to convey the resulting work.  The terms of this
License will continue to apply to the part which is the covered work,
but the special requirements of the GNU Affero General Public License,
section 13, concerning interaction through a network will apply to the
combination as such.

  14. Revised Versions of this License.

  The Free Software Foundation may publish revised and/or new versions of
the GNU General Public License from time to time.  Such new versions will
be similar in spirit to the present version, but may differ in detail to
address new problems or concerns.

  Each version is given a distinguishing version number.  If the
Program specifies that a certain numbered version of the GNU General
Public License "or any later version" applies to it, you have the
option of following the terms and conditions either of that numbered
version or of any later version published by the Free Software
Foundation.  If the Program does not specify a version number of the
GNU General Public License, you may choose any version ever published
by the Free Software Foundation.

  If the Program specifies that a proxy can decide which future
versions of the GNU General Public License can be used, that proxy's
public statement of acceptance of a version permanently authorizes you
to choose that version for the Program.

  Later license versions may give you additional or different
permissions.  However, no additional obligations are imposed on any
author or copyright holder as a result of your choosing to follow a
later version.

  15. Disclaimer of Warranty.

  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

  16. Limitation of Liability.

  IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MODIFIES AND/OR CONVEYS
THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY
GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE
USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF
DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD
PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS),
EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF
SUCH DAMAGES.

  17. Interpretation of Sections 15 and 16.

  If the disclaimer of warranty and limitation of liability provided
above cannot be given local legal effect according to their terms,
reviewing courts shall apply local law that most closely approximates
an absolute waiver of all civil liability in connection with the
Program, unless a warranty or assumption of liability accompanies a
copy of the Program in return for a fee.

                     END OF TERMS AND CONDITIONS

            How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
state the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

Also add information on how to contact you by electronic and paper mail.

  If the program does terminal interaction, make it output a short
notice like this when it starts in an interactive mode:

    <program>  Copyright (C) <year>  <name of author>
    This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
    This is free software, and you are welcome to redistribute it
    under certain conditions; type `show c' for details.

The hypothetical commands `show w' and `show c' should show the appropriate
parts of the General Public License.  Of course, your program's commands
might be different; for a GUI interface, you would use an "about box".

  You should also get your employer (if you work as a programmer) or school,
if any, to sign a "copyright disclaimer" for the program, if necessary.
For more information on this, and how to apply and follow the GNU GPL, see
<https://www.gnu.org/licenses/>.

  The GNU General Public License does not permit incorporating your program
into proprietary programs.  If your program is a subroutine library, you
may consider it more useful to permit linking proprietary applications with
the library.  If this is what you want to do, use the GNU Lesser General
Public License instead of this License.  But first, please read
<https://www.gnu.org/licenses/why-not-lgpl.html>.

``````
