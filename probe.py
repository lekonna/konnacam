import serial
import tkinter as tk
import pygubu
import cv2
import numpy as np
from datetime import datetime
from PIL import Image,ImageTk
from dxfwrite import DXFEngine as dxf

COMPORT = 'COM4'
#COMPORT = None
width = 800
height = 600

CAM = True
CAM = False
"""
TODO:
- add circle, and line for dxf
- add save button that prompts a savefile name

"""

class Appis:
    def __init__(self, master):
        ################################################################
        # UI init
        ################################################################
        self.master = master
        self.builder = builder = pygubu.Builder()
        builder.add_from_file('probe.ui')
        self.mainwindow = builder.get_object('mainwindow',master)
        self.master.title("KonnaCAM")
        builder.connect_callbacks(self)
        self.canv = self.builder.get_object('Display_canvas')
        self.fps_text = None
        self.Scrollbar = self.builder.get_object('Scrollbar')
        self.Pointlist_textfield = self.builder.get_object('Pointlist_textfield')
        self.Scrollbar.config(command=self.Pointlist_textfield.yview)
        self.Pointlist_textfield.config(yscrollcommand=self.Scrollbar.set)

        ################################################################
        # Member variable initit
        ################################################################
        self.step_size = self.builder.tkvariables['step_size'].get()
        self.device_x = 0
        self.device_y = 0
        self.device_z = 0

        self.machine_x = 0
        self.machine_y = 0
        self.machine_z = 0

        self.pointlist_txt = ""
        self.pointlist = []
        self.fast_toggle = False
        ################################################################
        # Keyboard bindings
        ################################################################
        self.master.bind('<Left>',self.device_move_x_neg)
        self.master.bind('<Right>',self.device_move_x_pos)
        self.master.bind('<Up>',self.device_move_y_neg)
        self.master.bind('<Down>',self.device_move_y_pos)
        self.master.bind('<Prior>',self.device_move_z_pos)
        self.master.bind('<Next>',self.device_move_z_neg)
        self.master.bind('<space>',self.store_machine_point)
        self.master.bind('<Shift_L>',self.fast_move_toggle)
        self.master.bind('+',self.focus_in)
        self.master.bind('-',self.focus_out)
        self.master.bind('s',self.save_dxf)
        self.builder.get_object('Speed_1000x_button',self.master).bind('<Up>',lambda e:None)

        ################################################################
        # USB camera setup
        ################################################################
        if(CAM):
            self.cap=cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,height)
            self.cam_focus = 120
            self.cap.set(28,self.cam_focus)
        self.mainwindow.after(10,self.show_frame)
        self.frame = 0
        self.t_first = datetime.now()
        ################################################################
        # Cam ui setup
        ################################################################
        self.cam_circle    = False
        self.cam_crosshair = True
        self.big_image     = False
        self.r = 40
        ################################################################
        # Device communication setup
        ################################################################
        self.builder.tkvariables['status'].set('Status: DISCONNECTED')
        self.move_command = "G00"
        self.ser = None
    def connect_machine(self):
        if(COMPORT):
            ser = serial.Serial(COMPORT,9600,
                        bytesize=serial.SEVENBITS,stopbits=serial.STOPBITS_TWO,
                        timeout=0,parity=serial.PARITY_EVEN,xonxoff=True)
            self.ser = ser
            self.device_command("G91\r\n")
            self.device_command("G91\r\n")
        self.builder.tkvariables['status'].set('Status: CONNECTED')
    def focus_in(self,event):
        print("focus")
        self.cam_focus -= 5
        if(self.cam_focus<0): self.cam_focus = 0
        self.cap.set(28,self.cam_focus)
        return 'break'

    def focus_out(self,event):
        self.cam_focus += 5
        if(self.cam_focus>255): self.cam_focus = 255
        self.cap.set(28,self.cam_focus)
        return 'break'

    def show_frame(self):
        self.frame += 1
        if(self.frame>30):
            t_delta = datetime.now()-self.t_first
            fps = self.frame/(t_delta.total_seconds())
            if(not self.fps_text):
                self.fps_text = self.canv.create_text((740,10),text=f'fps {fps:.2f}',anchor=tk.NW,fill='#00FF00',state=tk.NORMAL)
            else:
                self.canv.itemconfig(self.fps_text,text=f'fps {fps:.2f}')
            self.frame = 0
            self.t_first = datetime.now()
        if(CAM): _,frame = self.cap.read()
        else: frame = cv2.imread("tempimg.jpg")
        zoom = cv2.resize(frame[height//2-50:height//2+50,width//2-50:width//2+50],(200,200))
        edge = cv2.cvtColor(frame[height//2-150:height//2+150,width//2-150:width//2+150],cv2.COLOR_BGR2GRAY)
        edge = cv2.Canny(edge,80,160)
        edge = cv2.cvtColor(edge,cv2.COLOR_GRAY2RGBA)
        cv2image = cv2.cvtColor(frame,cv2.COLOR_BGR2RGBA)
        cv2zoom  = cv2.cvtColor(zoom,cv2.COLOR_BGR2RGBA)

        img = Image.fromarray(cv2image)
        zoomimg = Image.fromarray(cv2zoom)
        edgeimg = Image.fromarray(edge)

        self.imgtk = ImageTk.PhotoImage(image=img)
        self.zoomtk = ImageTk.PhotoImage(image=zoomimg)
        self.edgeimg = ImageTk.PhotoImage(image=edgeimg)

        if(not self.big_image):
            self.big_image = self.canv.create_image((0,0),image=self.imgtk,anchor=tk.NW,state=tk.NORMAL)
            self.zoom_image =self.canv.create_image((0,0),image=self.zoomtk,anchor=tk.NW,state=tk.NORMAL)
            self.edge_image = self.canv.create_image((width-300,0),image=self.edgeimg,anchor=tk.NW,state=tk.HIDDEN)
        else:
            self.canv.itemconfig(self.big_image,image=self.imgtk)
            self.canv.itemconfig(self.zoom_image,image=self.zoomtk)
            self.canv.itemconfig(self.edge_image,image=self.edgeimg)

        if(self.cam_crosshair):
            self.cross1 = Crosshair(self.canv,[width/2,height/2],[width,height],self.r)
            self.cross2 = Crosshair(self.canv,[100,100],[200,200],1)
            self.cross3 = Crosshair(self.canv,[width-150,150],[300,300],self.r)
            self.change_circle_r()
            self.cam_crosshair = False
            self.edge_toggle()
            self.zoom_toggle()

        self.mainwindow.after(1,self.show_frame)
    def edge_toggle(self):
        if(self.builder.tkvariables['edge_enable'].get()):
            self.cross3.show()
            self.canv.itemconfig(self.edge_image,state=tk.NORMAL)
        else:
            self.cross3.hide()
            self.canv.itemconfig(self.edge_image,state=tk.HIDDEN)

    def zoom_toggle(self):
        if(self.builder.tkvariables['zoom_enable'].get()):
            self.cross2.show()
            self.canv.itemconfig(self.zoom_image,state=tk.NORMAL)
        else:
            self.cross2.hide()
            self.canv.itemconfig(self.zoom_image,state=tk.HIDDEN)
    def change_circle_r(self):
        entry = self.builder.get_object('Circle_Entry',self.master).get()
        if(entry.isdigit()):
            if(int(entry)!=self.r):
                self.r=int(entry)
                self.cross1.change_r(self.r)
                self.cross3.change_r(self.r)
        self.mainwindow.after(500,self.change_circle_r)
    def save_dxf(self,event):
        drawing = dxf.drawing("temp.dxf")
        for point in self.pointlist:
            drawing.add(dxf.point(point))
        drawing.save()
        drawing = dxf.drawing("temp2d.dxf")
        for point in self.pointlist:
            drawing.add(dxf.circle(1,(point[0],point[1])))

        drawing.save()
    def fast_move_toggle(self,event):
        self.fast_toggle = not self.fast_toggle
        if(self.fast_toggle):
            self.step_size  = 10
        else:
            self.step_size = self.builder.tkvariables['step_size'].get()
        print(self.step_size)


    def update_displays(self):
        y_str = f'{self.device_y:03.3f}'
        self.builder.tkvariables['device_y'].set(y_str)
        x_str = f'{self.device_x:03.3f}'
        self.builder.tkvariables['device_x'].set(x_str)
        z_str = f'{self.device_z:03.3f}'
        self.builder.tkvariables['device_z'].set(z_str)


        my_str = f'{self.machine_y:03.3f}'
        self.builder.tkvariables['machine_y'].set(my_str)
        mx_str = f'{self.machine_x:03.3f}'
        self.builder.tkvariables['machine_x'].set(mx_str)
        mz_str = f'{self.machine_z:03.3f}'
        self.builder.tkvariables['machine_z'].set(mz_str)

        #print(x_str,y_str,z_str)


    def set_step_size(self):
        self.step_size = self.builder.tkvariables['step_size'].get()
    def zero_all(self):
        print("zeroing device")
        self.device_x = 0
        self.device_z = 0
        self.device_y = 0
        self.update_displays()

    def zero_all_machine(self):
        print("zeroing machine")
        self.machine_x = 0
        self.machine_y = 0
        self.machine_z = 0
        self.update_displays()

    def halve_x(self):
        self.device_x /= 2
        self.update_displays()

    def halve_y(self):
        self.device_y /= 2
        self.update_displays()

    def halve_z(self):
        self.device_z /= 2
        self.update_displays()

    def zero_x(self):
        self.device_x = 0
        self.update_displays()

    def zero_y(self):
        self.device_y = 0
        self.update_displays()

    def zero_z(self):
        self.device_z = 0
        self.update_displays()

    def device_move_y_pos(self,event=None):
        self.device_move(y=self.step_size)
        return 'break'

    def device_move_y_neg(self,event=None):
        self.device_move(y=-self.step_size)
        return 'break'

    def device_move_x_pos(self,event=None):
        self.device_move(x=self.step_size)
        return 'break'

    def device_move_x_neg(self,event=None):
        self.device_move(x=-self.step_size)
        return 'break'

    def device_move_z_pos(self,event=None):
        self.device_move(z=self.step_size)
        return 'break'

    def device_move_z_neg(self,event=None):
        self.device_move(z=-self.step_size)
        return 'break'

    def device_move_to_z_zero(self):
        print("running device to z zero")
        self.device_move(z=-self.device_z)

    def device_move(self,x=0,y=0,z=0):
        self.device_x += x
        self.device_y += y
        self.device_z += z
        self.machine_x += x
        self.machine_y += y
        self.machine_z += z

        move = f"{self.move_command} X{x:03.3f}  Y{y:03.3f} Z{z:03.3f}\r\n"
        self.device_command(move)
        #print(move)
        self.update_displays()
    def device_command(self,g):
        if(self.ser):
            self.ser.writelines([g.encode('ascii')])
        print(g)

    def device_move_to_xy_zero(self):
        print("running device to x,y zero")
        self.device_move(x=-self.device_x,y=-self.device_y)

    def store_machine_point(self,event=None):
        self.pointlist.append((self.machine_x,self.machine_y,self.machine_z))
        x_str = f'{self.machine_x:03.3f}'
        y_str = f'{self.machine_y:03.3f}'
        z_str = f'{self.machine_z:03.3f}'
        line = x_str+" "+y_str+" "+z_str+"\n"
        pl = self.builder.get_object('Pointlist_textfield')
        pl.insert(tk.INSERT,line)
        if(len(self.pointlist)>6):
            self.Pointlist_textfield.yview(tk.END)
        return 'break'
    def delete_last(self):
        if(not self.pointlist): return
        self.pointlist.pop()
        self.Pointlist_textfield.delete('1.0','end')
        for x,y,z in self.pointlist:
            self.Pointlist_textfield.insert(tk.INSERT,f'{x:03.3f} {y:03.3f} {z:03.3f}\n')
        self.Pointlist_textfield.yview(tk.END)
    def clear_points(self):
        self.pointlist = []
        pl = self.builder.get_object('Pointlist_textfield')
        pl.delete('1.0',"end")
        pl.update()
class Crosshair:
    def __init__(self, canv, location, size,r):
        self.line1 = canv.create_line(location[0]-size[0]/2,location[1],location[0]+size[0]/2,location[1],fill='#00FF00')
        self.line2 = canv.create_line(location[0],location[1]-size[1]/2,location[0],location[1]+size[1]/2,fill='#00FF00')
        self.circle = canv.create_oval(location[0]-r/2,location[1]-r/2,location[0]+r/2,location[1]+r/2,outline='#00FF00')
        self.canv = canv
        self.location = location
    def show(self):
        self.canv.itemconfig(self.line1,state=tk.NORMAL)
        self.canv.itemconfig(self.line2,state=tk.NORMAL)
        self.canv.itemconfig(self.circle,state=tk.NORMAL)
    def hide(self):
        self.canv.itemconfig(self.line1,state=tk.HIDDEN)
        self.canv.itemconfig(self.line2,state=tk.HIDDEN)
        self.canv.itemconfig(self.circle,state=tk.HIDDEN)
    def change_r(self,r):
        self.canv.coords(self.circle,self.location[0]-r/2,self.location[1]-r/2,self.location[0]+r/2,self.location[1]+r/2)
if __name__ == '__main__':
    root = tk.Tk()
    app = Appis(root)
    root.mainloop()
