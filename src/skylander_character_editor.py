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
ELEMENT_COLORS={"Magic":"#a879ff","Water":"#48aaff","Fire":"#ff765e","Life":"#70d65f","Undead":"#a89cff","Earth":"#e6ad5b","Air":"#51d4d0","Tech":"#f28c38","Light":"#ffe16a","Dark":"#c19aff","Unknown":"#91a0ad"}
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
  super().__init__(parent,width=width,height=height,bg=background,highlightthickness=1,highlightbackground=border,highlightcolor=border,takefocus=True,cursor="hand2")
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
  super().__init__();self.title("Skylander Character Editor");self.geometry("1200x720");self.minsize(1120,700);self.files=[];self.current=0;self.folder_selection=False
  self.bg="#14171b";self.surface="#1d232a";self.panel="#222a32";self.inset="#2b343e";self.text="#f5f7fa";self.muted="#b4bec9";self.accent=ELEMENT_COLORS["Unknown"];self.configure(bg=self.bg)
  self._buttons=[]
  outer=tk.Frame(self,bg=self.bg,padx=28,pady=22);outer.pack(fill="both",expand=True)
  outer.grid_columnconfigure(0,weight=1);outer.grid_rowconfigure(3,weight=1)
  header=tk.Frame(outer,bg=self.bg);header.grid(row=0,column=0,sticky="ew",pady=(0,16))
  tk.Label(header,text="Skylander Character Editor",font=("TkDefaultFont",25,"bold"),bg=self.bg,fg=self.text,anchor="center").pack(fill="x")
  tk.Label(header,text="Customize figure level and gold",font=("TkDefaultFont",12),bg=self.bg,fg=self.muted,anchor="center").pack(fill="x",pady=(4,0))
  self.accent_bar=tk.Frame(outer,bg=self.accent,height=3);self.accent_bar.grid(row=1,column=0,sticky="ew",pady=(0,16))
  actions=tk.Frame(outer,bg=self.bg,height=52);actions.grid(row=2,column=0,sticky="ew",pady=(0,18));actions.grid_propagate(False)
  self.choose_files_button=self.button(actions,"Choose Files…",self.filespick)
  self.choose_folder_button=self.button(actions,"Choose Folder…",self.folderpick)
  self.clear_button=self.button(actions,"Clear",lambda:self.setfiles([]))
  for index,button in enumerate((self.choose_files_button,self.choose_folder_button,self.clear_button)):
   actions.grid_columnconfigure(index,weight=1,uniform="actions")
   button.grid(row=0,column=index,sticky="nsew",padx=(0 if index==0 else 7,0 if index==2 else 7))
  self._drop_buttons={}
  self._register_drop_target(self.choose_files_button,"files")
  self._register_drop_target(self.choose_folder_button,"folder")
  body=tk.Frame(outer,bg=self.bg);body.grid(row=3,column=0,sticky="nsew");body.grid_propagate(False)
  left_column=tk.Frame(body,bg=self.bg);left_column.pack(side="left",fill="both",expand=True,padx=(0,16))
  self.card=tk.Frame(left_column,bg=self.surface,highlightthickness=1,highlightbackground=self.accent,padx=14,pady=14)
  self.card.pack(fill="both",expand=True)
  self._navigation_visible=False
  self._layout_mode=None
  self.figure_panel=tk.Frame(self.card,bg=self.surface);self.figure_panel.pack(fill="both",expand=True)
  self.empty_preview=tk.Label(self.figure_panel,text="Select a file or folder to preview a Skylander.",bg=self.surface,fg=self.muted,font=("TkDefaultFont",15),justify="center",wraplength=560)
  self.navigation_group=tk.Frame(self.figure_panel,bg=self.surface);self.navigation_group.pack(expand=True)
  self.navigation_group.grid_columnconfigure(1,weight=0)
  self.back=self.button(self.navigation_group,"‹",lambda:self.move(-1),secondary=True,width=48)
  self.back.grid(row=0,column=0,padx=(0,18),sticky="e")
  self.back.grid_remove()
  self.figure_content=tk.Frame(self.navigation_group,bg=self.surface)
  self.counter_label=tk.Label(self.figure_content,text="",bg=self.surface,fg=self.muted,font=("TkDefaultFont",12,"bold"))
  # Keep one canvas mounted at a constant size; only the artwork coordinates
  # change between figure orientations, avoiding macOS Tk resize repaint gaps.
  self.art=tk.Canvas(self.figure_content,width=496,height=409,bg=self.surface,highlightthickness=0)
  self.art.place(x=0,y=0,width=496,height=409)
  self._portrait_image=None
  self.info_panel=tk.Frame(self.figure_content,bg=self.inset,width=240,height=377,highlightthickness=1,highlightbackground="#39434e")
  self.info_panel.grid_propagate(False)
  self.info_identity=tk.Frame(self.info_panel,bg=self.inset,padx=14,pady=14)
  self.name=tk.StringVar(value="No figure selected");self.name_label=tk.Label(self.info_identity,textvariable=self.name,font=("TkDefaultFont",20,"bold"),bg=self.inset,fg=self.accent,anchor="w",justify="left",wraplength=210);self.name_label.pack(fill="x",pady=(0,10))
  self.game=tk.StringVar(value="")
  self.kind=tk.StringVar(value="")
  self.element=tk.StringVar(value="")
  self.meta_labels=[]
  for label,var in (("GAME",self.game),("TYPE",self.kind),("ELEMENT",self.element)):
   tk.Label(self.info_identity,text=label,font=("TkDefaultFont",9,"bold"),bg=self.inset,fg=self.muted,anchor="w").pack(fill="x",pady=(0,2))
   value_label=tk.Label(self.info_identity,textvariable=var,font=("TkDefaultFont",13),bg=self.inset,fg=self.text,justify="left",anchor="w",wraplength=250)
   value_label.pack(fill="x",pady=(0,6));self.meta_labels.append(value_label)
  self.info_separator=tk.Frame(self.info_panel,bg="#3b4651",height=1)
  self.info_progress=tk.Frame(self.info_panel,bg=self.inset,padx=14,pady=12)
  tk.Label(self.info_progress,text="CURRENT STATS",font=("TkDefaultFont",9,"bold"),bg=self.inset,fg=self.muted,anchor="w").pack(fill="x",pady=(0,7))
  self.stats=tk.StringVar(value="")
  self.stats_label=tk.Label(self.info_progress,textvariable=self.stats,font=("TkDefaultFont",14,"bold"),bg=self.inset,fg=self.text,justify="left",anchor="w",wraplength=210);self.stats_label.pack(fill="x",pady=(0,12))
  tk.Label(self.info_progress,text="SELECTED FILE",font=("TkDefaultFont",9,"bold"),bg=self.inset,fg=self.muted,anchor="w").pack(fill="x",pady=(0,5))
  self.filelabel=tk.StringVar(value="")
  self.file_label=tk.Label(self.info_progress,textvariable=self.filelabel,bg=self.inset,fg=self.text,font=("TkDefaultFont",11),justify="left",anchor="w",wraplength=210);self.file_label.pack(fill="x")
  self.forward=self.button(self.navigation_group,"›",lambda:self.move(1),secondary=True,width=48)
  self.forward.grid(row=0,column=2,padx=(18,0),sticky="w")
  self.forward.grid_remove()
  panel=tk.Frame(body,bg=self.panel,highlightthickness=1,highlightbackground="#39434e",padx=22,pady=22,width=300);self.settings_panel=panel;panel.pack(side="right",fill="y");panel.pack_propagate(False)
  self.settings_title=tk.Label(panel,text="BATCH SETTINGS",font=("TkDefaultFont",12,"bold"),bg=self.panel,fg=self.accent);self.settings_title.pack(anchor="w",pady=(0,24))
  self.lv=tk.IntVar(value=20);self.gold=tk.IntVar(value=65000)
  tk.Label(panel,text="Level",bg=self.panel,fg=self.text,font=("TkDefaultFont",13,"bold")).pack(anchor="w")
  self.level_entry=tk.Entry(panel,textvariable=self.lv,width=12,font=("TkDefaultFont",15,"bold"),relief="flat",bd=0,bg=self.inset,fg=self.text,insertbackground=self.text,justify="center",highlightthickness=1,highlightbackground="#485461",highlightcolor=self.accent)
  self.level_entry.pack(anchor="w",fill="x",pady=(8,12),ipady=12)
  self.button(panel,"Set max level",lambda:self.lv.set(20),secondary=True).pack(fill="x",pady=(0,24))
  tk.Label(panel,text="Gold",bg=self.panel,fg=self.text,font=("TkDefaultFont",13,"bold")).pack(anchor="w")
  self.gold_entry=tk.Entry(panel,textvariable=self.gold,width=12,font=("TkDefaultFont",15,"bold"),relief="flat",bd=0,bg=self.inset,fg=self.text,insertbackground=self.text,justify="center",highlightthickness=1,highlightbackground="#485461",highlightcolor=self.accent)
  self.gold_entry.pack(anchor="w",fill="x",pady=(8,12),ipady=12)
  self.button(panel,"Set max gold",lambda:self.gold.set(65000),secondary=True).pack(fill="x",pady=(0,24))
  self.apply_button=self.button(outer,"Apply to all selected files",self.apply,primary=True);self.apply_button.grid(row=4,column=0,sticky="ew",pady=(16,0))
  self.status=tk.StringVar(value="Choose files, set their stats, then apply as copies or edit in place.")
  self.is_swap_force=False
  self._layout_figure(False)
  self.show_current()
 def button(self,parent,text,command,secondary=False,primary=False,width=None):
  background=self.accent if primary else self.panel
  foreground=contrast_text(background) if primary else self.text
  font_size=21 if text in ("‹","›") else 12
  button=ActionButton(parent,text,command,background,foreground,self.accent,("TkDefaultFont",font_size,"bold" if primary or text in ("‹","›") else "normal"),width=width if width is not None else 260,height=48 if width is not None else 48)
  button._is_primary=primary;button._base_text=text;button._base_font=("TkDefaultFont",font_size,"bold" if primary or text in ("‹","›") else "normal");button._base_pady=13
  self._buttons.append(button)
  if primary:self.primary_button=button
  return button
 def _layout_figure(self,swap_force):
  """Arrange a fixed-size portrait preview and its matching information card."""
  mode="swap" if swap_force else "portrait"
  if mode==self._layout_mode:return
  self._layout_mode=mode
  self.counter_label.place_forget()
  self.info_panel.grid_forget()
  for widget in (self.info_identity,self.info_separator,self.info_progress):
   widget.pack_forget();widget.grid_forget();widget.place_forget()
  self.navigation_group.grid_columnconfigure(0,weight=0);self.navigation_group.grid_columnconfigure(1,weight=0);self.navigation_group.grid_columnconfigure(2,weight=0)
  if swap_force:
   art_width,art_height=494,184
   info_height=184;counter_height=32;content_gap=9
   self.figure_content.configure(width=art_width+2,height=counter_height+art_height+content_gap+info_height);self.figure_content.grid_propagate(False)
   self.info_panel.configure(width=art_width,height=info_height,highlightthickness=1,highlightbackground=self.accent);self.info_panel.grid_propagate(False)
   self.info_identity.configure(padx=10,pady=8);self.info_progress.configure(padx=10,pady=8)
   self.name_label.configure(wraplength=190,font=("TkDefaultFont",17,"bold"));self.name_label.pack_configure(pady=(0,3))
   for label in self.meta_labels:label.configure(wraplength=190,font=("TkDefaultFont",11));label.pack_configure(pady=(0,2))
   self.stats_label.configure(wraplength=190,font=("TkDefaultFont",12,"bold"));self.stats_label.pack_configure(pady=(0,5))
   self.file_label.configure(wraplength=190,font=("TkDefaultFont",10))
   column_minimum=(art_width-6)//2
   self.info_panel.grid_columnconfigure(0,weight=1,minsize=column_minimum);self.info_panel.grid_columnconfigure(1,weight=1,minsize=column_minimum);self.info_panel.grid_columnconfigure(2,weight=0,minsize=0)
   self.info_identity.grid(row=0,column=0,sticky="nsew")
   self.info_separator.configure(bg="#657381",width=1,height=160);self.info_separator.place(relx=0.5,rely=0.5,anchor="center",height=160)
   self.info_progress.grid(row=0,column=1,sticky="nsew")
   self.info_separator.lift()
   self.info_panel.place(x=0,y=art_height+counter_height+content_gap,width=art_width,height=info_height)
  else:
   art_width,art_height=240,377
   counter_height=32
   gap=14
   # Keep both portrait columns the same fixed height and prevent grid's
   # requested-size negotiation from shrinking the detail card.
   self.figure_content.configure(width=art_width*2+gap+2,height=counter_height+art_height);self.figure_content.grid_propagate(False)
   self.info_panel.configure(width=240,height=377,highlightthickness=1,highlightbackground=self.accent);self.info_panel.grid_propagate(False)
   self.info_identity.configure(padx=14,pady=14);self.info_progress.configure(padx=14,pady=12)
   self.name_label.configure(wraplength=210,font=("TkDefaultFont",20,"bold"));self.name_label.pack_configure(pady=(0,10))
   for label in self.meta_labels:label.configure(wraplength=210,font=("TkDefaultFont",12));label.pack_configure(pady=(0,6))
   self.stats_label.configure(wraplength=210,font=("TkDefaultFont",14,"bold"));self.stats_label.pack_configure(pady=(0,12))
   self.file_label.configure(wraplength=210,font=("TkDefaultFont",11))
   self.info_identity.pack(fill="x");self.info_separator.configure(bg="#3b4651",width=1,height=0);self.info_separator.pack(fill="x",padx=20,pady=(0,0));self.info_progress.pack(fill="x")
   self.info_panel.place(x=art_width+gap,y=counter_height,width=art_width,height=art_height)
  self.navigation_group.grid_columnconfigure(1,weight=1)
  self.figure_content.grid(row=0,column=1,sticky="n")
  composition_height=art_height+(info_height+content_gap if swap_force else 0)
  arrow_vertical_pad=counter_height+max(0,(composition_height-48)//2)
  self.back.grid_configure(row=0,column=0,padx=(0,18),pady=(arrow_vertical_pad,0),sticky="ne")
  self.forward.grid_configure(row=0,column=2,padx=(18,0),pady=(arrow_vertical_pad,0),sticky="nw")
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
   self.is_swap_force=False;self._layout_figure(False)
   self.navigation_group.pack_forget();self.empty_preview.place(relx=0.5,rely=0.5,anchor="center")
   self.name.set("No figure selected");self.game.set("Choose a file");self.kind.set("");self.element.set("");self.stats.set("");self.filelabel.set("");self.accent=ELEMENT_COLORS["Unknown"]
   self.apply_theme();self.update_navigation();self.update_idletasks();return
  self.empty_preview.place_forget()
  if not self.navigation_group.winfo_manager():self.navigation_group.pack(expand=True)
  p=self.files[self.current]
  info=None;variant_info=None;image_name=None;self.is_swap_force=False
  try:
   raw=Path(p).read_bytes()
   if len(raw)!=1024:raise ValueError(f"Expected 1,024 bytes; got {len(raw)}.")
   toy,info,variant_info=figure_info(raw)
   self.is_swap_force=1000<=toy<=1015 or 2000<=toy<=2015
   try:
    _,_,xp,gold,_=inspect(p)
    self.stats.set(f"Level {level_for(xp)}  ·  Gold {gold:,}")
   except Exception:
    self.stats.set("Progress data unavailable")
   if info:
    display_name=variant_info.get("name",info["name"]) if variant_info else info["name"]
    element=info.get("element","Unknown");game=info.get("game","Skylanders");kind=info.get("type","Skylander")
    self.name.set(display_name);self.game.set(game);self.kind.set(kind);self.element.set(f"{element} element");self.accent=ELEMENT_COLORS.get(element,ELEMENT_COLORS["Unknown"])
    image_name=variant_info.get("image") if variant_info else info.get("image")
   else:
    self.name.set(f"Unknown figure (ID {toy})");self.game.set("Unknown game");self.kind.set("Unknown type");self.element.set("Unknown element");self.accent=ELEMENT_COLORS["Unknown"]
  except Exception as e:self.name.set("Unable to read figure");self.game.set("File details unavailable");self.kind.set("");self.element.set("");self.stats.set("Progress data unavailable");self.accent=ELEMENT_COLORS["Unknown"]
  self.filelabel.set(p.name);self._layout_figure(self.is_swap_force);self.draw_art(image_name,toy if info else None);self.apply_theme();self.update_navigation();self.update_idletasks()
  width=max(1,self.art.winfo_width());height=max(1,self.art.winfo_height())
  self.art.event_generate("<Expose>",x=0,y=0,width=width,height=height,when="now")
  if self.folder_selection and len(self.files)>1:
   self.counter_label.event_generate("<Expose>",x=0,y=0,width=max(1,self.counter_label.winfo_width()),height=max(1,self.counter_label.winfo_height()),when="now")
  self.update_idletasks()
 def update_navigation(self):
  visible=self.folder_selection and len(self.files)>1
  if visible:
   self.counter_label.configure(text=f"{self.current+1} / {len(self.files)}")
   self.counter_label.place(relx=0.5,y=0,anchor="n",height=24)
   self.counter_label.lift()
  else:
   self.counter_label.configure(text="")
   self.counter_label.place_forget()
  if visible==self._navigation_visible:return
  self._navigation_visible=visible
  if visible:
   self.back.grid()
   self.forward.grid()
  else:
   self.back.grid_remove();self.forward.grid_remove()
 def apply_theme(self):
  fg=contrast_text(self.accent)
  self.card.configure(highlightbackground=self.accent)
  self.settings_panel.configure(highlightbackground=self.accent)
  self.accent_bar.configure(bg=self.accent)
  self.name_label.configure(fg=self.accent);self.settings_title.configure(fg=self.accent);self.info_panel.configure(highlightbackground=self.accent)
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
  art_canvas=self.art
  art_canvas.configure(bg=self.surface)
  canvas_width,canvas_height=(494,184) if self.is_swap_force else (240,377)
  image_center_y=32+canvas_height//2
  next_item=None;next_image=None
  if image_name:
   image_path=APP_ROOT/"assets"/"portraits"/Path(image_name).name
   if image_path.is_file():
    try:
     portrait=Image.open(image_path).convert("RGBA")
     portrait=portrait.resize((canvas_width,canvas_height),Image.Resampling.LANCZOS)
     portrait=ImageTk.PhotoImage(portrait,master=self)
     next_image=portrait
     next_item=art_canvas.create_image(canvas_width//2,image_center_y,image=portrait,anchor="center",tags=("portrait-next",))
    except (OSError,ValueError,tk.TclError):pass
  if next_item is None:
   next_item=art_canvas.create_text(canvas_width//2,image_center_y,text="Portrait unavailable",font=("TkDefaultFont",11),fill=self.muted,tags=("portrait-next",))
  art_canvas.delete("portrait-content")
  art_canvas.addtag_withtag("portrait-content","portrait-next")
  art_canvas.dtag("portrait-next")
  self._portrait_image=next_image
 def setfiles(self,x,from_folder=False):
  self.files=[Path(p) for p in x];self.folder_selection=from_folder;self.current=0;self.show_current()
  if not x:self.status.set("Choose files, set their stats, then apply as copies or edit in place.")
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
 def _choose_apply_mode(self,lv,g,uninitialized):
  dialog=tk.Toplevel(self)
  dialog.title("Apply changes")
  dialog.transient(self)
  dialog.resizable(False,False)
  dialog.configure(bg=self.panel)
  choice={"mode":None}
  content=tk.Frame(dialog,bg=self.panel,padx=28,pady=24)
  content.pack(fill="both",expand=True)
  tk.Label(content,text="How should the changes be saved?",font=("TkDefaultFont",15,"bold"),bg=self.panel,fg=self.text).pack(anchor="w")
  tk.Label(content,text=f"{len(self.files)} file(s) · Level {lv} · Gold {g:,}",font=("TkDefaultFont",11),bg=self.panel,fg=self.muted).pack(anchor="w",pady=(6,14))
  tk.Label(content,text="Copies are saved beside the originals with a _copy suffix; existing names get a number.",font=("TkDefaultFont",10),bg=self.panel,fg=self.muted,wraplength=420,justify="left").pack(anchor="w",pady=(0,14))
  if uninitialized:
   tk.Label(content,text=f"A fresh progress save will be initialized for {uninitialized} uninitialized figure(s).",font=("TkDefaultFont",10),bg=self.panel,fg=self.muted,wraplength=420,justify="left").pack(anchor="w",pady=(0,14))
  buttons=tk.Frame(content,bg=self.panel);buttons.pack(fill="x")
  def finish(mode):
   choice["mode"]=mode
   dialog.destroy()
  copies=ActionButton(buttons,"Create copies (Recommended)",lambda:finish("copy"),self.accent,contrast_text(self.accent),self.accent,("TkDefaultFont",10,"bold"),width=420,height=48)
  copies.pack(fill="x",pady=(0,9))
  inplace=ActionButton(buttons,"Edit files in place",lambda:finish("in_place"),self.panel,self.text,self.accent,("TkDefaultFont",10,"normal"),width=420,height=48)
  inplace.pack(fill="x",pady=(0,9))
  cancel=ActionButton(buttons,"Cancel",lambda:finish(None),self.panel,self.muted,self.accent,("TkDefaultFont",10,"normal"),width=420,height=42)
  cancel.pack(fill="x")
  dialog.bind("<Escape>",lambda event:finish(None))
  dialog.bind("<Return>",lambda event:finish("copy"))
  dialog.protocol("WM_DELETE_WINDOW",lambda:finish(None))
  copies.focus_set()
  dialog.update_idletasks()
  x=self.winfo_rootx()+(self.winfo_width()-dialog.winfo_width())//2
  y=self.winfo_rooty()+(self.winfo_height()-dialog.winfo_height())//2
  dialog.geometry(f"+{x}+{y}")
  self.wait_window(dialog)
  return choice["mode"]
 def _copy_destination(self,path,reserved):
  path=Path(path)
  candidate=path.with_name(f"{path.stem}_copy{path.suffix}")
  index=2
  while candidate.exists() or candidate in reserved:
   candidate=path.with_name(f"{path.stem}_copy_{index}{path.suffix}")
   index+=1
  reserved.add(candidate)
  return candidate
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
  mode=self._choose_apply_mode(lv,g,len(uninit))
  if mode is None:return
  ok=0;bad=[]
  reserved=set()
  for p in self.files:
   tmp=p.with_name(p.name+".skyeditor.tmp")
   destination=p if mode=="in_place" else self._copy_destination(p,reserved)
   try:
    edit(p,tmp,lv,g)
    if mode=="copy":
     if destination.exists():destination=self._copy_destination(p,reserved)
     tmp.replace(destination)
    else:tmp.replace(p)
    ok+=1
   except Exception as e:bad.append(f"{p.name}: {e}")
   finally:
    if tmp.exists():tmp.unlink()
  self.show_current()
  action="Created copies from" if mode=="copy" else "Updated"
  self.status.set(f"{action} {ok}; failed {len(bad)}.")
  if bad:messagebox.showwarning("Finished",f"{action} {ok}; failed {len(bad)}.\n\n"+"\n".join(bad[:6]),parent=self)
  else:
   message=(f"Created {ok} edited copy/copies beside the originals. Original files were left unchanged." if mode=="copy" else f"Updated {ok} file(s) in place. Filenames unchanged.")
   messagebox.showinfo("Success",message,parent=self)
if __name__=="__main__":App().mainloop()
