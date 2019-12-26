# konnacam
Code for using old fanuc cnc machines and a usb camera to measure stuff

## requirements

pc with python and usb cam with serial connection to fanuc machine. I'm using an 1990 Fanuc Series 0-M
use at your own risk, put all rapids to very low at first and be ready to press the reset :)

## usage
install the required dependencies with pip, set the COM settings in the script, connect a USB camera
(the code i guess is assuming you use logitech) set the camera device number, and run the program.

Set the machine in drip feed mode, and do cycle start. After this press the "connect" button in the UI,
the script will put the machine in G91 incremental mode, and all the movements will be just the
step size in the desired direction. 

Pressing 'shift' will make the machine move in 10mm increments

## measuring

there are two sets of cordinates, first one is a global machine cordinate which is used to store the
points, the second one is a helper which you can use to find centers of things by utilizing the zeroing
and halving functionality. the Machine to X Y zero will run the machine to the zero of the second cordinate
system

