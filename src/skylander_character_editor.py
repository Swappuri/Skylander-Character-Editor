#!/usr/bin/env python3
from pathlib import Path
from hashlib import md5
import json
import sys
import tkinter as tk
from tkinter import filedialog,messagebox
from PIL import Image,ImageTk
from tkinterdnd2 import DND_FILES,TkinterDnD
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
CONST=b" Copyright (C) 2010 Activision. All Rights Reserved. "
MAX_GOLD=65000
LEVEL_XP={1:0,2:1000,3:2200,4:3800,5:6000,6:9000,7:13000,8:18000,9:24000,10:33000,11:43000,12:55000,13:70000,14:87000,15:106000,16:126000,17:147000,18:169000,19:184000,20:199535}
# IDs are read from the unencrypted figure header. Keep this catalog conservative:
# unknown figures are identified by ID instead of showing a guessed name/element.
ELEMENT_COLORS={"Magic":"#a879ff","Water":"#48aaff","Fire":"#ff765e","Life":"#70d65f","Undead":"#a89cff","Earth":"#e6ad5b","Air":"#51d4d0","Tech":"#b2c7d8","Light":"#ffe16a","Dark":"#c19aff","Unknown":"#91a0ad"}
def contrast_text(hex_color):
 rgb=[int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
 lum=sum(weight*(channel/12.92 if channel<=0.04045 else ((channel+0.055)/1.055)**2.4) for weight,channel in zip((0.2126,0.7152,0.0722),rgb))
 white=(1.05)/(lum+0.05);dark=(lum+0.05)/0.05
 return "#ffffff" if white>=dark else "#101318"
def blend_color(start,end,fraction):
 a=tuple(int(start[i:i+2],16) for i in (1,3,5));b=tuple(int(end[i:i+2],16) for i in (1,3,5))
 return "#"+"".join(f"{round(x+(y-x)*fraction):02x}" for x,y in zip(a,b))

class ActionButton(tk.Frame):
 """A fixed-size, fully clickable frame and label control."""
 def __init__(self,parent,text,command,background,foreground,border,font,width=260,height=48):
  super().__init__(parent,width=width,height=height,bg=background,highlightthickness=2,highlightbackground=border,highlightcolor=border,takefocus=True,cursor="hand2")
  self._button_options={"text":text,"command":command,"bg":background,"fg":foreground,"activebackground":background,"activeforeground":foreground,"highlightbackground":border,"highlightcolor":border,"font":font,"pady":13,"state":"normal"}
  self._hovered=False
  self._label=tk.Label(self,text=text,bg=background,fg=foreground,font=font,cursor="hand2",anchor="center")
  self._label.pack(fill="both",expand=True,padx=10,pady=8)
  self.pack_propagate(False)
  self.bind("<Enter>",self._hover_enter)
  self.bind("<Leave>",self._hover_leave)
  self.bind("<ButtonPress-1>",self._mouse_press)
  self.bind("<ButtonRelease-1>",lambda event:"break")
  self._label.bind("<Enter>",self._hover_enter)
  self._label.bind("<Leave>",self._hover_leave)
  self._label.bind("<ButtonPress-1>",self._mouse_press)
  self._label.bind("<ButtonRelease-1>",lambda event:"break")
  self.bind("<Return>",lambda event:self.invoke())
  self.bind("<space>",lambda event:self.invoke())
 def configure(self,cnf=None,**kw):
  if isinstance(cnf,dict):kw={**cnf,**kw}
  if not kw:return super().configure()
  for key,value in kw.items():
   if key in self._button_options:self._button_options[key]=value
  frame_options={key:value for key,value in kw.items() if key in ("bg","highlightbackground","highlightcolor","cursor","width","height")}
  if frame_options:super().configure(**frame_options)
  label_options={key:value for key,value in kw.items() if key in ("bg","fg","font","cursor")}
  if "text" in kw:label_options["text"]=kw["text"]
  if self._hovered and "bg" in label_options:label_options["bg"]=self._hover_color()
  if label_options:self._label.configure(**label_options)
  if self._hovered and "bg" in frame_options:super().configure(bg=self._hover_color())
 def config(self,cnf=None,**kw):return self.configure(cnf,**kw)
 def cget(self,key):return self._button_options[key] if key in self._button_options else super().cget(key)
 def __getitem__(self,key):return self.cget(key)
 def __setitem__(self,key,value):self.configure(**{key:value})
 def _hover_color(self):
  o=self._button_options
  return blend_color(o["bg"],"#ffffff",0.08) if o["bg"]==o["highlightbackground"] else blend_color(o["bg"],o["highlightbackground"],0.18)
 def _hover_enter(self,event):
  self._hovered=True;self.configure(bg=self._button_options["bg"])
 def _hover_leave(self,event):
  self._hovered=False;self.configure(bg=self._button_options["bg"])
 def _mouse_press(self,event):
  # Trigger on mouse-down so macOS cannot swallow a later mouse-up after an
  # app activation or dialog focus transition. The bound canvas covers the
  # complete visible control, including its label.
  if self._button_options["state"]!="disabled":self.invoke()
  return "break"
 def invoke(self):
  if self._button_options["state"]!="disabled" and self._button_options["command"]:return self._button_options["command"]()
APP_ROOT=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parents[1]))
try:
 CHARACTER_CATALOG=json.loads((APP_ROOT/"assets"/"skylanders_db.json").read_text(encoding="utf-8"))
except (OSError,ValueError):
 CHARACTER_CATALOG={}

def figure_info(raw):
 toy=int.from_bytes(raw[0x10:0x12],"little")
 record=CHARACTER_CATALOG.get(f"{toy:06X}")
 if not record:return toy,None,None
 variant=int.from_bytes(raw[0x1C:0x1E],"little")
 variant_key=f"{variant:04X}"
 variant_record=record.get("variants",{}).get(variant_key)
 return toy,record,variant_record
INITIALIZABLE_CHARACTER_TYPES={
 "Skylander", "Giant", "LightCore", "Swapper", "Trap Master",
 "SuperCharger", "Sensei",
}

# Shared fresh standard-character save skeleton. Skylanders use the same mirrored
# progress-area layout across game generations. Keep the figure identity/UID intact;
# only initialize progress-area blocks before writing the requested XP and gold.
FRESH_CHARACTER_BLOCKS={
 0x24:bytes.fromhex("00000000000700000001a5f8aea1f159"),
 0x25:bytes.fromhex("00000000000001010000000000000000"),
 0x29:bytes.fromhex("140d1b09ea070000000000000e081901"),
 0x2A:bytes.fromhex("140d1b09ea0700000000000000000000"),
 0x2C:bytes.fromhex("c7ff0180ff0000000000000000000000"),
 0x2D:bytes.fromhex("545b0100000000000000000000000000"),
}
def aes(d,k,dec=False):
 c=Cipher(algorithms.AES(k),modes.ECB()); x=c.decryptor() if dec else c.encryptor(); return x.update(d)+x.finalize()
def transform(d,dec):
 o=bytearray(d); h=bytes(d[:32])
 for b in range(8,64):
  if b%4==3: continue
  i=b*16
  block=bytes(d[i:i+16])
  # New/unused save blocks are stored as literal zeroes, not AES ciphertext.
  # Preserve them in both directions until real data is written there.
  if block==b"\x00"*16:
   o[i:i+16]=block
   continue
  k=md5(h+bytes([b])+CONST).digest()
  o[i:i+16]=aes(block,k,dec)
 return o
def crc16(d):
 c=0xffff
 for x in d:
  c^=x<<8
  for _ in range(8): c=(((c<<1)^0x1021) if c&0x8000 else c<<1)&0xffff
 return c
def newer(a,b): return 0<((a-b)&255)<128
def copyblocks(p,s,t,ds):
 for d in ds: p[(t+d)*16:(t+d+1)*16]=p[(s+d)*16:(s+d+1)*16]
def crc1(p,b):
 o=b*16; return crc16(bytes(p[o:o+14])+b"\x05\x00")
def crc2(p,b):
 a=b*16;c=(b+1)*16;d=(b+3)*16;e=(b+4)*16
 return crc16(b"\x06\x01"+bytes(p[a+2:a+16])+bytes(p[c:c+16])+bytes(p[d:d+16])+bytes(p[e:e+16]))
def valid_a(p,b):
 o=b*16
 return bytes(p[o:o+16])!=b"\x00"*16 and int.from_bytes(p[o+14:o+16],"little")==crc1(p,b)

def valid_b(p,b):
 o=b*16
 return bytes(p[o:o+16])!=b"\x00"*16 and int.from_bytes(p[o:o+2],"little")==crc2(p,b)

def choose_valid(p,b0,b1,seqoff,validator):
 v0,v1=validator(p,b0),validator(p,b1)
 if v0 and v1:
  s0=p[b0*16+seqoff]; s1=p[b1*16+seqoff]
  return b1 if newer(s1,s0) else b0
 if v0:return b0
 if v1:return b1
 return None

def active(p):
 return (choose_valid(p,0x08,0x24,9,valid_a),
         choose_valid(p,0x11,0x2d,2,valid_b))

def inspect(path):
 r=bytearray(Path(path).read_bytes())
 if len(r)!=1024: raise ValueError(f"Expected 1024 bytes; got {len(r)}.")
 toy=int.from_bytes(r[0x10:0x12],"little"); p=transform(r,True); a,b=active(p)
 # A factory-new/uninitialized character has no valid progress save yet.
 if a is None and b is None:
  return toy,p,0,0,"uninitialized"
 if a is None or b is None:
  raise ValueError("Progress save is incomplete or damaged; no edit was performed.")
 oa=a*16;ob=b*16
 xp=int.from_bytes(p[oa:oa+3],"little")+int.from_bytes(p[ob+3:ob+5],"little")+int.from_bytes(p[ob+8:ob+12],"little")
 gold=int.from_bytes(p[oa+3:oa+5],"little")
 return toy,p,xp,gold,"initialized"
def level_for(x):
 n=1
 for lv,t in LEVEL_XP.items():
  if x>=t:n=lv
 return n
def splitxp(t):
 a=min(t,33000);r=max(0,t-33000);b=min(r,63500);return a,b,max(0,r-63500)
def initialize_character_plain(raw,lv,g):
 toy=int.from_bytes(raw[0x10:0x12],"little")
 record=CHARACTER_CATALOG.get(f"{toy:06X}")
 if not record or record.get("type") not in INITIALIZABLE_CHARACTER_TYPES:
  raise ValueError("Fresh-save initialization is supported for recognized character figures, not this figure type or unknown ID.")
 p=transform(raw,True)
 aa,bb=active(p)
 if aa is not None or bb is not None:
  raise ValueError("Figure already has progress data; normal editing should be used instead.")

 # Preserve the selected figure's complete identity/read-only region and sector
 # trailers. Populate the shared standard-character progress structure.
 for b,data in FRESH_CHARACTER_BLOCKS.items():
  p[b*16:(b+1)*16]=data

 x1,x2,x3=splitxp(LEVEL_XP[lv])
 oa=0x24*16; ob=0x2D*16
 p[oa:oa+3]=x1.to_bytes(4,"little")[:3]
 p[oa+3:oa+5]=g.to_bytes(2,"little")
 p[oa+9]=1
 p[ob+2]=1
 p[ob+3:ob+5]=x2.to_bytes(2,"little")
 p[ob+8:ob+12]=x3.to_bytes(4,"little")

 # Recalculate the checksums used by the already-validated reader/writer.
 p[oa+14:oa+16]=crc1(p,0x24).to_bytes(2,"little")
 p[ob:ob+2]=crc2(p,0x2D).to_bytes(2,"little")
 return p

def initialize_fresh_character(src,dst,lv,g):
 raw=bytearray(Path(src).read_bytes())
 if len(raw)!=1024: raise ValueError("Not a 1024-byte regular figure dump.")
 p=initialize_character_plain(raw,lv,g)
 enc=transform(p,False)
 if transform(enc,True)!=p:
  raise ValueError("Encryption round-trip validation failed.")
 Path(dst).write_bytes(enc)
 _,_,xp_check,gold_check,state=inspect(dst)
 if state!="initialized" or xp_check!=LEVEL_XP[lv] or gold_check!=g:
  Path(dst).unlink(missing_ok=True)
  raise ValueError("Fresh-save initialization validation failed; original was left unchanged.")

def edit(src,dst,lv,g):
 raw=bytearray(Path(src).read_bytes())
 if len(raw)!=1024: raise ValueError("Not a 1024-byte regular figure dump.")
 p=transform(raw,True)
 aa,bb=active(p)
 if aa is None and bb is None:
  return initialize_fresh_character(src,dst,lv,g)
 if aa is None or bb is None:
  raise ValueError("Progress save is incomplete or damaged; refusing to guess or overwrite it.")

 # Write to the opposite redundant mirror, preserving the existing proven workflow.
 sa=aa; da=0x24 if sa==0x08 else 0x08
 sb=bb; db=0x2d if sb==0x11 else 0x11
 na=(p[sa*16+9]+1)&255
 nb=(p[sb*16+2]+1)&255
 copyblocks(p,sa,da,[0,1,2,4,5,6,8])
 copyblocks(p,sb,db,[0,1,3,4])

 x1,x2,x3=splitxp(LEVEL_XP[lv]);oa,ob=da*16,db*16
 p[oa:oa+3]=x1.to_bytes(4,"little")[:3]
 p[oa+3:oa+5]=g.to_bytes(2,"little")
 p[oa+9]=na
 p[oa+14:oa+16]=crc1(p,da).to_bytes(2,"little")
 p[ob+2]=nb
 p[ob+3:ob+5]=x2.to_bytes(2,"little")
 p[ob+8:ob+12]=x3.to_bytes(4,"little")
 p[ob:ob+2]=crc2(p,db).to_bytes(2,"little")

 enc=transform(p,False)
 if transform(enc,True)!=p: raise ValueError("Encryption verification failed.")
 # Re-open the produced dump through the normal parser before allowing replacement.
 Path(dst).write_bytes(enc)
 _,_,xp_check,gold_check,state=inspect(dst)
 if state!="initialized" or xp_check!=LEVEL_XP[lv] or gold_check!=g:
  Path(dst).unlink(missing_ok=True)
  raise ValueError("Post-write validation failed; original was left unchanged.")

class App(TkinterDnD.Tk):
 def __init__(self):
  super().__init__();self.title("Skylander Character Editor");self.geometry("1040x760");self.minsize(860,680);self.files=[];self.current=0;self.folder_selection=False
  self.bg="#15181c";self.surface="#20252b";self.panel="#252b32";self.text="#f4f6f8";self.muted="#b7c0c9";self.accent=ELEMENT_COLORS["Unknown"];self.configure(bg=self.bg)
  self._buttons=[]
  outer=tk.Frame(self,bg=self.bg,padx=24,pady=20);outer.pack(fill="both",expand=True)
  tk.Label(outer,text="Skylander Character Editor",font=("TkDefaultFont",22,"bold"),bg=self.bg,fg=self.text,anchor="center").pack(fill="x")
  tk.Label(outer,text="Set level and gold for one figure or a whole folder.",font=("TkDefaultFont",10),bg=self.bg,fg=self.muted,anchor="center").pack(fill="x",pady=(3,16))
  self.accent_bar=tk.Frame(outer,bg=self.accent,height=3);self.accent_bar.pack(fill="x",pady=(0,14))
  body=tk.Frame(outer,bg=self.bg);body.pack(fill="both",expand=True)
  left_column=tk.Frame(body,bg=self.bg);left_column.pack(side="left",fill="both",expand=True,padx=(0,14))
  actions=tk.Frame(left_column,bg=self.bg,height=44);actions.pack(fill="x",pady=(0,14));actions.pack_propagate(False)
  self.choose_files_button=self.button(actions,"Choose Files…",self.filespick)
  self.choose_folder_button=self.button(actions,"Choose Folder…",self.folderpick)
  self.clear_button=self.button(actions,"Clear",lambda:self.setfiles([]))
  for index,button in enumerate((self.choose_files_button,self.choose_folder_button,self.clear_button)):
   actions.grid_columnconfigure(index,weight=1,uniform="actions")
   button.grid(row=0,column=index,sticky="nsew",padx=4)
  self._drop_buttons={}
  self._register_drop_target(self.choose_files_button,"files")
  self._register_drop_target(self.choose_folder_button,"folder")
  self.card=tk.Frame(left_column,bg=self.surface,highlightthickness=2,highlightbackground=self.accent,padx=14,pady=14)
  self.card.pack(fill="both",expand=True)
  self.counter=tk.StringVar(value="")
  self._navigation_visible=False
  preview=tk.Frame(self.card,bg=self.surface);preview.pack(fill="both",expand=True)
  self.back=self.button(preview,"‹",lambda:self.move(-1),secondary=True,width=44)
  self.figure_panel=tk.Frame(preview,bg=self.surface);self.figure_panel.pack(fill="both",expand=True)
  self.forward=self.button(preview,"›",lambda:self.move(1),secondary=True,width=44)
  self.figure_stack=tk.Frame(self.figure_panel,bg=self.surface);self.figure_stack.pack(expand=True)
  self.counter_label=tk.Label(self.figure_stack,textvariable=self.counter,bg=self.surface,fg=self.muted,font=("TkDefaultFont",12))
  self.art=tk.Canvas(self.figure_stack,width=340,height=180,bg=self.surface,highlightthickness=0);self.art.pack(pady=(8,4))
  self.name=tk.StringVar(value="No figure selected");self.name_label=tk.Label(self.figure_stack,textvariable=self.name,font=("TkDefaultFont",20,"bold"),bg=self.surface,fg=self.text);self.name_label.pack()
  self.detail=tk.StringVar(value="Choose .sky or .dump files to preview their figure details.")
  self.detail_label=tk.Label(self.figure_stack,textvariable=self.detail,font=("TkDefaultFont",12),bg=self.surface,fg=self.muted,justify="center",wraplength=520);self.detail_label.pack(pady=(7,10))
  self.stats=tk.StringVar(value="")
  self.stats_label=tk.Label(self.figure_stack,textvariable=self.stats,font=("TkDefaultFont",13,"bold"),bg=self.surface,fg=self.text,justify="center");self.stats_label.pack(pady=(0,10))
  self.filelabel=tk.StringVar(value="")
  self.file_label=tk.Label(self.figure_stack,textvariable=self.filelabel,bg=self.surface,fg=self.muted,font=("TkDefaultFont",11),wraplength=520);self.file_label.pack()
  panel=tk.Frame(body,bg=self.panel,highlightthickness=2,highlightbackground=self.accent,padx=24,pady=24,width=340);self.settings_panel=panel;panel.pack(side="right",fill="y");panel.pack_propagate(False)
  self.settings_title=tk.Label(panel,text="BATCH SETTINGS",font=("TkDefaultFont",10,"bold"),bg=self.panel,fg=self.accent);self.settings_title.pack(anchor="w",pady=(0,22))
  self.lv=tk.IntVar(value=20);self.gold=tk.IntVar(value=65000)
  tk.Label(panel,text="Level",bg=self.panel,fg=self.text,font=("TkDefaultFont",12)).pack(anchor="w")
  self.level_entry=tk.Entry(panel,textvariable=self.lv,width=12,font=("TkDefaultFont",12),relief="flat",bd=0,bg="#343b44",fg=self.text,insertbackground=self.text,justify="center",highlightthickness=2,highlightbackground="#46515c",highlightcolor=self.accent)
  self.level_entry.pack(anchor="w",fill="x",pady=(8,18),ipady=14)
  self.button(panel,"Set max level",lambda:self.lv.set(20),secondary=True).pack(fill="x",pady=(0,26))
  tk.Label(panel,text="Gold",bg=self.panel,fg=self.text,font=("TkDefaultFont",12)).pack(anchor="w")
  self.gold_entry=tk.Entry(panel,textvariable=self.gold,width=12,font=("TkDefaultFont",12),relief="flat",bd=0,bg="#343b44",fg=self.text,insertbackground=self.text,justify="center",highlightthickness=2,highlightbackground="#46515c",highlightcolor=self.accent)
  self.gold_entry.pack(anchor="w",fill="x",pady=(8,18),ipady=14)
  self.button(panel,"Set max gold",lambda:self.gold.set(65000),secondary=True).pack(fill="x",pady=(0,26))
  tk.Frame(panel,bg=self.panel).pack(fill="both",expand=True)
  tk.Label(panel,text="Applies to all selected files.",bg=self.panel,fg=self.muted,wraplength=220,justify="left",font=("TkDefaultFont",11)).pack(anchor="w",fill="x",pady=(8,4))
  self.apply_button=self.button(outer,"Apply to all selected files",self.apply,primary=True);self.apply_button.pack(fill="x",pady=(14,8))
  self.status=tk.StringVar(value="Files are edited in place after validation.")
  self.show_current()
 def button(self,parent,text,command,secondary=False,primary=False,width=None):
  background=self.accent if primary else self.panel
  foreground=contrast_text(background) if primary else self.text
  button=ActionButton(parent,text,command,background,foreground,self.accent,("TkDefaultFont",10,"bold" if primary else "normal"),width=112 if width is not None else 260,height=54 if width is not None else 48)
  button._is_primary=primary;button._base_text=text;button._base_font=("TkDefaultFont",10,"bold" if primary else "normal");button._base_pady=13
  self._buttons.append(button)
  if primary:self.primary_button=button
  return button
 def _register_drop_target(self,button,kind):
  button.drop_target_register(DND_FILES)
  button._label.drop_target_register(DND_FILES)
  button.dnd_bind("<<DropEnter>>",lambda event,b=button:self._drop_enter(event,b))
  button.dnd_bind("<<DropLeave>>",lambda event,b=button:self._drop_leave(event,b))
  button.dnd_bind("<<Drop>>",lambda event,b=button,k=kind:self._drop_items(event,b,k))
  button._label.dnd_bind("<<DropEnter>>",lambda event,b=button:self._drop_enter(event,b))
  button._label.dnd_bind("<<DropLeave>>",lambda event,b=button:self._drop_leave(event,b))
  button._label.dnd_bind("<<Drop>>",lambda event,b=button,k=kind:self._drop_items(event,b,k))
  self._drop_buttons[button]={"text":button._base_text,"font":button._base_font,"pady":button._base_pady,"background":button.cget("bg"),"foreground":button.cget("fg"),"color":button.cget("bg"),"after":None,"inside":False}
 def _drop_enter(self,event,button):
  state=self._drop_buttons[button];state["inside"]=True
  button.configure(text="+",font=("TkDefaultFont",26,"bold"),pady=0)
  self._animate_drop_color(button,self.accent,contrast_text(self.accent))
  return getattr(event,"action","copy")
 def _drop_leave(self,event,button):
  self._drop_buttons[button]["inside"]=False
  self._animate_drop_color(button,self.panel,self.text)
  return getattr(event,"action","copy")
 def _animate_drop_color(self,button,target_color,target_foreground):
  state=self._drop_buttons[button]
  if state["after"] is not None:
   self.after_cancel(state["after"]);state["after"]=None
  start_color=state["color"];start_foreground=button.cget("fg");steps=12
  def tick(index=1):
   fraction=min(1,index/steps)
   color=blend_color(start_color,target_color,fraction)
   foreground=blend_color(start_foreground,target_foreground,fraction)
   button.configure(bg=color,activebackground=color,fg=foreground,activeforeground=foreground)
   state["color"]=color
   if index<steps:state["after"]=self.after(18,lambda:tick(index+1))
   else:
    state["after"]=None
    if not state["inside"]:
     button.configure(text=state["text"],font=state["font"],pady=state["pady"],bg=state["background"],fg=state["foreground"],activebackground=self.surface,activeforeground=self.text)
  tick()
 def _drop_items(self,event,button,kind):
  self._drop_leave(event,button)
  paths=[Path(value) for value in self.tk.splitlist(event.data)]
  if kind=="files":
   files=[path for path in paths if path.is_file() and path.suffix.lower() in (".sky",".dump")]
   if files:self.setfiles(files)
   else:messagebox.showinfo("No Skylander files","Drop one or more .sky or .dump files on Choose Files.",parent=self)
  else:
   folders=[path for path in paths if path.is_dir()]
   if folders:self.load_folder(folders[0])
   else:messagebox.showinfo("Choose a folder","Drop a folder on Choose Folder.",parent=self)
  return getattr(event,"action","copy")
 def load_folder(self,folder):
  files=sorted((path for path in Path(folder).iterdir() if path.is_file() and path.suffix.lower() in (".sky",".dump")),key=lambda path:path.name.lower())
  if files:self.setfiles(files,from_folder=True)
  else:messagebox.showinfo("No files","No .sky or .dump files found directly in that folder.",parent=self)
 def move(self,delta):
  if self.files:self.current=(self.current+delta)%len(self.files);self.show_current()
 def show_current(self):
  if not self.files:
   self.name.set("No figure selected");self.detail.set("Choose .sky or .dump files to preview their figure details.");self.stats.set("");self.filelabel.set("");self.accent=ELEMENT_COLORS["Unknown"];self.draw_art(None);self.apply_theme();self.update_navigation();return
  p=self.files[self.current]
  info=None;variant_info=None;image_name=None
  try:
   raw=Path(p).read_bytes()
   if len(raw)!=1024:raise ValueError(f"Expected 1,024 bytes; got {len(raw)}.")
   toy,info,variant_info=figure_info(raw)
   try:
    _,_,xp,gold,_=inspect(p)
    self.stats.set(f"Level {level_for(xp)}  ·  Gold {gold:,}")
   except Exception:
    self.stats.set("Progress data unavailable")
   if info:
    display_name=variant_info.get("name",info["name"]) if variant_info else info["name"]
    element=info.get("element","Unknown");game=info.get("game","Skylanders");kind=info.get("type","Skylander")
    self.name.set(display_name);self.detail.set(f"{game}  ·  {kind}  ·  {element} element");self.accent=ELEMENT_COLORS.get(element,ELEMENT_COLORS["Unknown"])
    image_name=variant_info.get("image") if variant_info else info.get("image")
   else:
    self.name.set(f"Unknown figure (ID {toy})");self.detail.set("No matching character entry is available in the bundled catalog.");self.accent=ELEMENT_COLORS["Unknown"]
  except Exception as e:self.name.set("Unable to read figure");self.detail.set(str(e));self.stats.set("Progress data unavailable");self.accent=ELEMENT_COLORS["Unknown"]
  self.filelabel.set(p.name);self.draw_art(image_name,toy if info else None);self.apply_theme();self.update_navigation();self.update_idletasks()
 def update_navigation(self):
  visible=self.folder_selection and len(self.files)>1
  if visible:
   self.counter.set(f"{self.current+1} / {len(self.files)}")
  if visible==self._navigation_visible:return
  self._navigation_visible=visible
  if visible:
   self.counter_label.pack(before=self.art,pady=(0,8))
   self.figure_panel.pack_forget()
   self.back.pack(side="left",anchor="center",padx=(0,18))
   self.figure_panel.pack(side="left",fill="both",expand=True)
   self.forward.pack(side="right",anchor="center",padx=(18,0))
  else:
   self.back.pack_forget();self.counter_label.pack_forget();self.forward.pack_forget();self.counter.set("")
   self.figure_panel.pack_forget()
   self.figure_panel.pack(fill="both",expand=True)
 def apply_theme(self):
  fg=contrast_text(self.accent)
  self.card.configure(highlightbackground=self.accent)
  self.settings_panel.configure(highlightbackground=self.accent)
  self.accent_bar.configure(bg=self.accent)
  self.name_label.configure(fg=self.accent);self.settings_title.configure(fg=self.accent)
  self.level_entry.configure(highlightbackground=self.accent);self.gold_entry.configure(highlightbackground=self.accent)
  for button in self._buttons:
   bg=self.accent if button._is_primary else self.panel
   fg=contrast_text(bg) if button._is_primary else self.text
   button.configure(bg=bg,fg=fg,activebackground=self.surface,activeforeground=self.text,highlightbackground=self.accent,highlightcolor=self.accent)
   state=self._drop_buttons.get(button)
   if state:
    state["background"]=bg;state["foreground"]=fg
    if not state["inside"]:state["color"]=bg
 def draw_art(self,image_name,toy=None):
  self.art.delete("all");self.art.configure(bg=self.surface);self._portrait_image=None
  swap_force=toy is not None and (1000<=toy<=1015 or 2000<=toy<=2015)
  canvas_width,canvas_height=(380,210) if swap_force else (340,300)
  if self.folder_selection and len(self.files)>1:canvas_height-=30
  self.art.configure(width=canvas_width,height=canvas_height)
  if image_name:
   image_path=APP_ROOT/"assets"/"portraits"/Path(image_name).name
   if image_path.is_file():
    try:
     portrait=Image.open(image_path).convert("RGBA")
     portrait.thumbnail((canvas_width,canvas_height),Image.Resampling.LANCZOS)
     canvas_width,canvas_height=portrait.size
     self.art.configure(width=canvas_width,height=canvas_height)
     portrait=ImageTk.PhotoImage(portrait,master=self)
     self._portrait_image=portrait
     self.art.create_image(canvas_width//2,canvas_height//2,image=portrait,anchor="center")
     return
    except (OSError,ValueError,tk.TclError):pass
  self.art.create_text(canvas_width//2,canvas_height//2,text="Portrait unavailable",font=("TkDefaultFont",11),fill=self.muted)
 def setfiles(self,x,from_folder=False):
  self.files=[Path(p) for p in x];self.folder_selection=from_folder;self.current=0;self.show_current()
  if not x:self.status.set("Files are edited in place after validation.")
  if len(x)==1:
   try:
    _,_,xp,g,state=inspect(self.files[0])
    self.lv.set(level_for(xp));self.gold.set(min(g,MAX_GOLD))
    if state=="uninitialized":
     self.status.set("Current: Level 1, XP 0, gold 0 — uninitialized. A fresh standard-character progress save will be constructed when you apply changes.")
    else:
     self.status.set(f"Current: level {level_for(xp)}, XP {xp:,}, gold {g:,}")
   except Exception as e:self.status.set(str(e))
  elif x:self.status.set(f"Ready to apply the same stats to {len(x)} files.")
 def filespick(self):
  x=filedialog.askopenfilenames(parent=self,filetypes=[("Skylander dumps","*.sky *.dump"),("All files","*")]);
  self._restore_window_focus()
  if x:self.setfiles(x)
 def folderpick(self):
  d=filedialog.askdirectory(parent=self)
  self._restore_window_focus()
  if d:self.load_folder(d)
 def _restore_window_focus(self):
  def restore():
   if self.winfo_exists():
    self.lift()
    self.focus_force()
  self.after_idle(restore)
 def apply(self):
  if not self.files:return messagebox.showinfo("Select files","Select at least one .sky or .dump file.",parent=self)
  try:lv,g=int(self.lv.get()),int(self.gold.get())
  except:return messagebox.showerror("Invalid","Level and gold must be whole numbers.",parent=self)
  if not 1<=lv<=20 or not 0<=g<=65000:return messagebox.showerror("Invalid","Level must be 1–20; gold 0–65,000.",parent=self)
  uninit=[]
  for p in self.files:
   try:
    _,_,_,_,state=inspect(p)
    if state=="uninitialized": uninit.append(p)
   except: pass
  extra=""
  if uninit:
   extra=f"\n\nA fresh progress save will be initialized for {len(uninit)} uninitialized character figure(s)."
  if not messagebox.askyesno("Confirm",f"Modify {len(self.files)} file(s) in place?\n\nLevel {lv}\nGold {g:,}\n\nFilenames will stay unchanged.{extra}",parent=self):return
  ok=0;bad=[]
  for p in self.files:
   tmp=p.with_name(p.name+".skyeditor.tmp")
   try:
    edit(p,tmp,lv,g);tmp.replace(p);ok+=1
   except Exception as e:bad.append(f"{p.name}: {e}")
   finally:
    if tmp.exists():tmp.unlink()
  self.show_current()
  self.status.set(f"Updated {ok}; failed {len(bad)}.")
  if bad:messagebox.showwarning("Finished",f"Updated {ok}; failed {len(bad)}.\n\n"+"\n".join(bad[:6]),parent=self)
  else:messagebox.showinfo("Success",f"Updated {ok} file(s). Filenames unchanged.",parent=self)
if __name__=="__main__":App().mainloop()
