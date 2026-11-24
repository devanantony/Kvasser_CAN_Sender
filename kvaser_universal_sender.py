import sys, os, json, queue, threading, time, subprocess, math, re
from collections import defaultdict
import ast
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import can

BG = "#F5F3EE"
PANEL = "#FAF9F6"
FIELD = "#FFFFFF"
FG = "#243044"
MUTED = "#586578"
GREEN = "#16734D"
RED = "#B42338"

def modern_style(root):
    root.configure(bg=BG)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=PANEL, foreground=FG, font=("Segoe UI", 10), borderwidth=0)
    st.configure("TFrame", background=BG)
    st.configure("Card.TFrame", background=PANEL)
    st.configure("TLabelframe", background=PANEL, borderwidth=1, relief="solid", bordercolor="#D5D8DD")
    st.configure("TLabelframe.Label", background=PANEL, foreground=FG, font=("Segoe UI", 11, "bold"))
    st.configure("TLabel", background=PANEL, foreground=FG)
    st.configure("Title.TLabel", background=BG, foreground=FG, font=("Segoe UI", 15, "bold"))
    st.configure("Subtitle.TLabel", background=BG, foreground=MUTED)
    st.configure("TButton", background="#E5E8EC", foreground=FG, padding=(8,4), relief="flat")
    st.map("TButton", background=[("active", "#D8DFE8"), ("pressed", "#C8D2DF")])
    for name, base, hover in [("Primary", "#245dc1", "#3475e3"), ("Success", "#237C59", "#196747"), ("Danger", "#B43D4C", "#993342")]:
        st.configure(name+".TButton", background=base, foreground="#ffffff", padding=(8,4))
        st.map(name+".TButton", background=[("active",hover),("pressed",base)])
    st.configure("TEntry", fieldbackground=FIELD, foreground=FG, insertcolor=FG, padding=4, bordercolor="#B9C3CF", borderwidth=1)
    st.configure("TCombobox", fieldbackground=FIELD, foreground=FG, arrowcolor=FG, padding=3, bordercolor="#B9C3CF", selectbackground="#DCE8FA", selectforeground=FG)
    st.map("TCombobox", fieldbackground=[("readonly",FIELD)], foreground=[("readonly",FG)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    st.configure("TCheckbutton", background=PANEL, foreground=FG, padding=2, indicatorbackground=FIELD, indicatorforeground=FG)
    st.map("TCheckbutton", background=[("active",PANEL)], foreground=[("disabled",MUTED)], indicatorbackground=[("selected","#3475e3")])
    st.configure("Vertical.TScrollbar", background="#B9C3CF", troughcolor=BG, arrowcolor=FG)


WINDOWS = sys.platform == 'win32'
if WINDOWS:
    import can.interfaces.kvaser
    import can.interfaces.kvaser.canlib as kv
else:
    import can.interfaces.socketcan
SETTINGS = Path.home() / '.kvaser_universal.json'
WAKE = '40 ' + 'FF '*7 + '00 '*16

def command(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)

def discover():
    result = {}
    if WINDOWS:
        import ctypes
        for item in can.detect_available_configs(interfaces=['kvaser']):
            ch = item['channel']
            name = kv.get_channel_info(ch)
            cap = ctypes.c_uint32()
            try:
                kv.canGetChannelData(ch, 1, ctypes.byref(cap), ctypes.sizeof(cap))
                fd = bool(cap.value & 0x00080000)
            except Exception:
                fd = None
            result[str(ch)] = (str(name), fd)
    else:
        for p in Path('/sys/class/net').iterdir():
            try:
                if (p/'device/driver').resolve().name != 'kvaser_usb': continue
                info = json.loads(command(['ip','-j','-details','link','show',p.name]))[0]
                data = info.get('linkinfo',{}).get('info_data',{})
                fd = 'data_bittiming_const' in data or 'data_bittiming' in data or info.get('mtu') == 72
                dev = (p/'device').resolve()
                label = p.name
                for parent in [dev,*dev.parents]:
                    if (parent/'product').exists():
                        label = (parent/'product').read_text().strip()
                        if (parent/'serial').exists(): label += ' / '+(parent/'serial').read_text().strip()
                        break
                result[p.name] = (label, fd)
            except (OSError, ValueError, subprocess.SubprocessError): continue
    return result

class Channel:
    def __init__(self, app, key, info):
        self.app, self.key, self.info = app,key,info
        self.bus = None
        self.worker = None
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.frame = ttk.LabelFrame(app.inner,text=f'{key} — {info[0]} — '+('FD capable' if info[1] else 'Classic CAN' if info[1] is False else 'FD capability unknown'))
        self.frame.configure(padding=7)
        self.frame.pack(fill='x',padx=4,pady=3)
        for col in (1,3,5,7): self.frame.columnconfigure(col, weight=1)
        saved = app.saved.get(key,{})
        self.vars = {}
        defaults = dict(bitrate='500000',data_rate='2000000',fd_mode=bool(info[1]),id='123',payload='11 22 33 44 55 66 77 88',extended=False,fd=False,brs=False,interval='100',target='virtual' not in info[0].lower())
        for k,v in defaults.items():
            self.vars[k] = (tk.BooleanVar if isinstance(v,bool) else tk.StringVar)(value=saved.get(k,v))
        if info[1] is False:
            for k in ('fd_mode','fd','brs'): self.vars[k].set(False)
        for i,(k,label) in enumerate([('bitrate','Nominal bps'),('data_rate','Data bps'),('id','CAN ID hex'),('interval','Period ms')]):
            ttk.Label(self.frame,text=label).grid(row=0,column=i*2,sticky='w', padx=(4,2), pady=2)
            ttk.Entry(self.frame,textvariable=self.vars[k],width=12).grid(row=0,column=i*2+1,padx=4,sticky="ew")
        ttk.Label(self.frame,text='Payload').grid(row=1,column=0)
        ttk.Entry(self.frame,textvariable=self.vars['payload']).grid(row=1,column=1,columnspan=7,sticky='ew',pady=2)
        for i,(k,label) in enumerate([('fd_mode','FD bus'),('extended','Extended ID'),('fd','FD frame'),('brs','BRS'),('target','Broadcast target')]):
            w=ttk.Checkbutton(self.frame,text=label,variable=self.vars[k]); w.grid(row=2,column=i,sticky='w')
            if info[1] is False and k in ('fd_mode','fd','brs'): w.state(['disabled'])
        for i,(label,fn) in enumerate([('Connect',self.connect),('Disconnect',self.disconnect),('Wakeup preset',self.preset),('Send once',lambda:app.launch([self],self,False)),('Start periodic',lambda:app.launch([self],self,True)),('Stop',self.stop.set)]):
            ttk.Button(self.frame,text=label,command=fn,style=('Success.TButton' if label=='Connect' else 'Danger.TButton' if label in ('Stop','Disconnect') else 'Primary.TButton' if label in ('Send once','Start periodic') else 'TButton')).grid(row=3,column=i,padx=3,pady=3,sticky='w')
        self.status=ttk.Label(self.frame,text='Disconnected',foreground=RED); self.status.grid(row=4,column=0,columnspan=8,sticky='w')
        self.active_fd=False
    def preset(self):
        if self.info[1] is False: return messagebox.showerror('Preset','Wakeup requires CAN FD')
        for k,v in dict(id='1B000000',payload=WAKE.strip(),extended=True,fd=True,brs=True,fd_mode=True,interval='100').items(): self.vars[k].set(v)
    def get(self,k): return self.vars[k].get()
    def connect(self):
        if self.bus is not None: return
        try:
            rate=int(self.get('bitrate')); dr=int(self.get('data_rate')); fd=self.get('fd_mode')
            if rate<=0 or dr<=0: raise ValueError('Bitrates must be positive')
            if fd and self.info[1] is False: raise ValueError('FD unsupported')
            if WINDOWS:
                kwargs=dict(interface='kvaser',channel=int(self.key),bitrate=rate,fd=fd)
                if fd: kwargs['data_bitrate']=dr
            else:
                prefix=[] if os.geteuid()==0 else ['pkexec']
                ip=['ip','link','set',self.key]
                command(prefix+ip+['down'])
                args=['type','can','bitrate',str(rate),'restart-ms','100']
                if fd: args+=['dbitrate',str(dr),'fd','on']
                elif self.info[1]: args+=['fd','off']
                command(prefix+ip+args); command(prefix+ip+['up'])
                kwargs=dict(interface='socketcan',channel=self.key,fd=fd)
            self.bus=can.Bus(**kwargs); self.active_fd=fd
            self.app.log(f'{self.key}: connected')
            self.status.configure(text='Connected', foreground=GREEN)
            self.app.refresh_device_summary()
        except Exception as e: messagebox.showerror('Connection',str(e))
    def message(self):
        data=bytes.fromhex(self.get('payload')); fd=self.get('fd'); ext=self.get('extended')
        if fd and len(data) not in (*range(9),12,16,20,24,32,48,64): raise ValueError('Invalid FD payload length')
        return can.Message(arbitration_id=int(self.get('id'),16),data=data,is_extended_id=ext,is_fd=fd,bitrate_switch=fd and self.get('brs'),check=True)
    def disconnect(self):
        self.stop.set()
        if self.worker and self.worker.is_alive(): self.worker.join(timeout=1.5)
        if self.worker and self.worker.is_alive(): return False
        if self.bus is not None:
            try: self.bus.shutdown()
            except Exception as e: self.app.log(str(e))
            self.bus=None
        self.status.configure(text='Disconnected', foreground=RED)
        self.app.refresh_device_summary()
        return True
    def run(self,msg,period,gate):
        gate.wait()
        deadline=time.monotonic()
        try:
            while not self.stop.is_set():
                with self.lock: self.bus.send(msg,timeout=1.0)
                self.app.log(f'{self.key} TX queued ID={msg.arbitration_id:X} FD={msg.is_fd} BRS={msg.bitrate_switch} LEN={len(msg.data)} DATA={msg.data.hex(" ").upper()}')
                if period is None: break
                deadline += period
                now = time.monotonic()
                if deadline <= now:
                    deadline += (int((now-deadline)/period)+1)*period
                if self.stop.wait(max(0,deadline-time.monotonic())): break
        except Exception as e: self.app.log(f'{self.key} TX stopped: {e}')
    def diagnostics(self):
        if self.bus is None: return 'Disconnected'
        if WINDOWS: return f'Connected | {self.bus.state} (driver status)'
        d=json.loads(command(['ip','-j','-details','-statistics','link','show',self.key]))[0]
        x=d.get('linkinfo',{}).get('info_data',{})
        return f"Connected | {x.get('state','Unknown')} | error counters: {x.get('berr_counter','unavailable')} | TX: {'running' if self.worker and self.worker.is_alive() else 'idle'}"

class App:
    def __init__(self,root):
        self.root=root; root.title('Kvaser Universal CAN Tool'); root.geometry('1280x900'); root.minsize(1050,650); modern_style(root)
        self.channels={}; self.q=queue.Queue(maxsize=5000); self.saved={}
        try: self.saved=json.loads(SETTINGS.read_text())
        except (OSError,ValueError): pass
        header=ttk.Frame(root); header.pack(fill='x',padx=8,pady=(5,2))
        ttk.Label(header,text='KVASER / CAN WORKBENCH',style='Title.TLabel').pack(side='left')
        self.device_summary = tk.StringVar(value='Scanning Kvaser devices...')
        self.device_compact = tk.StringVar(value='Scanning...')
        ttk.Button(header,text='Device details',command=self.show_devices).pack(side='right',padx=(6,0))
        ttk.Label(header,textvariable=self.device_compact,style='Subtitle.TLabel',anchor='e',wraplength=620).pack(side='right',fill='x',expand=True)
        bar=ttk.Frame(root); bar.pack(fill='x',padx=8,pady=2)
        self.source=tk.StringVar()
        for label,fn in [('Scan devices',self.scan),('Connect all',lambda:[c.connect() for c in self.channels.values()]),('Disconnect all',lambda:[c.disconnect() for c in self.channels.values()]),('Save settings',self.save),('Stop all TX',lambda:[c.stop.set() for c in self.channels.values()])]:
            ttk.Button(bar,text=label,command=fn,style='Danger.TButton' if label in ('Stop all TX','Disconnect all') else 'Success.TButton' if label=='Connect all' else 'TButton').pack(side='left',padx=(0,4))
        b=ttk.Frame(root,style='Card.TFrame',padding=3); b.pack(fill='x',padx=8,pady=2)
        ttk.Label(b,text='Broadcast source:').pack(side='left',padx=3)
        self.sources=ttk.Combobox(b,textvariable=self.source,state='readonly',width=8); self.sources.pack(side='left')
        for label,periodic in [('Broadcast once',False),('Start broadcast',True)]: ttk.Button(b,text=label,command=lambda p=periodic:self.broadcast(p),style='Primary.TButton').pack(side='left',padx=4)
        ttk.Button(b,text='Start selected independently',command=self.start_independent,style='Success.TButton').pack(side='left',padx=4)
        area=ttk.Frame(root); area.pack(fill='both',expand=True,padx=5)
        cv=tk.Canvas(area,bg=BG,highlightthickness=0,yscrollincrement=20); sb=ttk.Scrollbar(area,command=cv.yview); cv.configure(yscrollcommand=sb.set); sb.pack(side='right',fill='y'); cv.pack(side='left',fill='both',expand=True)
        self.inner=ttk.Frame(cv); win=cv.create_window((0,0),window=self.inner,anchor='nw'); self.inner.bind('<Configure>',lambda e:cv.configure(scrollregion=cv.bbox('all'))); cv.bind('<Configure>',lambda e:cv.itemconfigure(win,width=e.width))
        self.channel_canvas = cv
        self.wheel_remainder = 0
        self.wheel_tag = 'ChannelListWheel'
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            root.bind_class(self.wheel_tag, sequence, self.scroll_channels)
        self.bind_channel_wheel(area)
        console=ttk.Frame(root,style='Card.TFrame',padding=4); console.pack(fill='x',padx=8,pady=4)
        toolbar=ttk.Frame(console,style='Card.TFrame'); toolbar.pack(fill='x',pady=(0,2))
        ttk.Label(toolbar,text='LIVE TRANSMISSION LOG',font=('Segoe UI',11,'bold')).pack(side='left')
        ttk.Button(toolbar,text='Clear log',command=self.clear).pack(side='right')
        self.logarea=logarea=ttk.Frame(console)
        self.log_toggle=ttk.Button(toolbar,text='Show log',command=self.toggle_log); self.log_toggle.pack(side='right',padx=4)
        self.output=tk.Text(logarea,height=5,state='disabled',bg=FIELD,fg=FG,font=('Consolas',10),relief='flat',padx=10,pady=8,wrap='none')
        logscroll=ttk.Scrollbar(logarea,command=self.output.yview); logscroll.pack(side='right',fill='y')
        self.output.configure(yscrollcommand=logscroll.set); self.output.pack(side='left',fill='both',expand=True)
        self.output.tag_configure('tx',foreground=GREEN); self.output.tag_configure('error',foreground=RED); self.output.tag_configure('info',foreground=MUTED)
        root.protocol('WM_DELETE_WINDOW',self.close); self.scan(); self.tick(); self.monitor()
    def toggle_log(self):
        if self.logarea.winfo_manager():
            self.logarea.pack_forget()
            self.log_toggle.configure(text='Show log')
        else:
            self.logarea.pack(fill='both')
            self.log_toggle.configure(text='Hide log')

    def show_devices(self):
        messagebox.showinfo('Detected Kvaser hardware', self.device_summary.get(), parent=self.root)

    def bind_channel_wheel(self, widget):
        tags = widget.bindtags()
        if self.wheel_tag not in tags:
            widget.bindtags((self.wheel_tag,) + tags)
        for child in widget.winfo_children():
            self.bind_channel_wheel(child)

    def scroll_channels(self, event):
        if getattr(event, 'num', None) == 4:
            steps = -1
        elif getattr(event, 'num', None) == 5:
            steps = 1
        else:
            self.wheel_remainder += event.delta
            steps = -int(self.wheel_remainder / 120)
            self.wheel_remainder += steps * 120
        if steps:
            self.channel_canvas.yview_scroll(steps * 3, 'units')
        return 'break'

    def log(self,s):
        try:self.q.put_nowait(time.strftime('%H:%M:%S')+' '+s+'\n')
        except queue.Full: pass
    def clear(self):
        self.output.configure(state='normal'); self.output.delete('1.0','end'); self.output.configure(state='disabled')
    def tick(self):
        self.output.configure(state='normal')
        for _ in range(300):
            try:
                line=self.q.get_nowait()
                tag='error' if any(x in line.lower() for x in ('error','tx stopped','failed')) else 'tx' if 'TX queued' in line else 'info'
                self.output.insert('end',line,tag)
            except queue.Empty:break
        if int(self.output.index('end-1c').split('.')[0])>3000:self.output.delete('1.0','1000.0')
        self.output.see('end'); self.output.configure(state='disabled'); self.root.after(100,self.tick)
    def scan(self):
        if any(c.worker and c.worker.is_alive() for c in self.channels.values()):
            self.log("Stop TX before scanning devices")
            return
        try: found=discover()
        except Exception as e:
            self.device_summary.set('Device detection failed'); self.device_compact.set('Detection failed')
            self.log(f'Detection error: {e}'); return
        for k,c in list(self.channels.items()):
            if k not in found or found[k]!=c.info:
                if c.disconnect():
                    self.saved[k]={n:v.get() for n,v in c.vars.items()}; c.frame.destroy(); del self.channels[k]; self.log(f'{k} removed')
        for k,info in found.items():
            if k not in self.channels: self.channels[k]=Channel(self,k,info); self.log(f'Detected {k}: {info}')
        self.bind_channel_wheel(self.inner)
        self.update_device_summary(found)
        self.sources.configure(values=list(self.channels))
        if self.source.get() not in self.channels:self.source.set(next(iter(self.channels),''))
    def refresh_device_summary(self):
        self.update_device_summary({k: c.info for k, c in self.channels.items()})
    def update_device_summary(self, found):
        if not found:
            self.device_summary.set('No Kvaser device detected'); self.device_compact.set('No Kvaser device detected')
            return
        groups = defaultdict(list)
        for key, (name, fd) in found.items():
            try:
                metadata = ast.literal_eval(name)
            except (ValueError, SyntaxError):
                metadata = {}
            if isinstance(metadata, dict) and 'device_name' in metadata:
                label = str(metadata['device_name'])
                serial = metadata.get('serial')
                port = metadata.get('dongle_channel', key)
            else:
                label = re.sub(r'\s*\(#\d+\)\s*$', '', name).strip()
                serial = None
                port = key
            mode = 'CAN FD' if fd else 'Classic CAN' if fd is False else 'FD unknown'
            channel = f'CH{port} (index {key})' if WINDOWS else key
            opened = key in self.channels and self.channels[key].bus is not None
            groups[(label, serial)].append((channel, mode, opened))
        lines = []
        for (label, serial), channels in groups.items():
            modes = {mode for _, mode, _ in channels}
            suffix = f' | {next(iter(modes))}' if len(modes) == 1 else ''
            count = sum(opened for _, _, opened in channels)
            state = 'Connected' if count == len(channels) else 'Disconnected' if count == 0 else 'Partially connected'
            lines.append(f'{label} — {len(channels)} CAN channel(s){suffix}')
            lines.append(f'{state} ({count}/{len(channels)} open)')
            for channel, mode, opened in channels:
                lines.append(f'{channel}: {mode} — '+('Connected' if opened else 'Disconnected'))
        connected = sum(k in self.channels and self.channels[k].bus is not None for k in found)
        lines.append(f'{len(found)} detected channel(s) | {connected} open | '+('CANlib' if WINDOWS else 'SocketCAN'))
        self.device_summary.set('\n'.join(lines))
        name = next(iter(groups))[0] if len(groups)==1 else f'{len(groups)} devices'
        self.device_compact.set(f'{name} | {len(found)} CH | {connected}/{len(found)} connected')
    def monitor(self):
        active = any(c.worker and c.worker.is_alive() for c in self.channels.values())
        if not active:
            self.scan()
        for c in self.channels.values():
            if c.worker and c.worker.is_alive():
                c.status.configure(text="Connected | TX running", foreground=GREEN)
                continue
            if active: continue
            try:c.status.configure(text=c.diagnostics(), foreground=GREEN if c.bus is not None else RED)
            except Exception as e:c.status.configure(text=str(e))
        self.root.after(3000,self.monitor)
    def launch(self,targets,source,periodic):
        try:
            if not targets:raise ValueError('Select targets')
            jobs = []
            for c in targets:
                cfg = source if source is not None else c
                msg = cfg.message(); period = float(cfg.get('interval'))/1000 if periodic else None
                if periodic and (not math.isfinite(period) or period<=0):raise ValueError('Invalid interval')
                if c.bus is None:raise ValueError(f'{c.key} not connected')
                if msg.is_fd and not c.active_fd:raise ValueError(f'{c.key} not connected in FD mode')
                if c.worker and c.worker.is_alive():raise ValueError(f'{c.key} already transmitting; stop first')
                jobs.append((c,msg,period))
            gate = threading.Event()
            started = []
            try:
                for c,msg,period in jobs:
                    own_msg = can.Message(arbitration_id=msg.arbitration_id, data=bytes(msg.data), is_extended_id=msg.is_extended_id, is_fd=msg.is_fd, bitrate_switch=msg.bitrate_switch, check=True)
                    c.stop.clear()
                    c.worker = threading.Thread(target=c.run, args=(own_msg,period,gate), daemon=True, name=f'CAN-TX-{c.key}')
                    c.worker.start()
                    started.append(c)
            except Exception:
                for c in started: c.stop.set()
                raise
            finally:
                gate.set()
        except Exception as e:messagebox.showerror('TX',str(e))
    def start_independent(self):
        self.launch([c for c in self.channels.values() if c.get("target")], None, True)
    def broadcast(self,periodic):
        if self.source.get() in self.channels:self.launch([c for c in self.channels.values() if c.get('target')],self.channels[self.source.get()],periodic)
    def save(self):
        self.saved.update({k:{n:v.get() for n,v in c.vars.items()} for k,c in self.channels.items()})
        try:SETTINGS.write_text(json.dumps(self.saved,indent=2)); self.log('Settings saved')
        except OSError as e:self.log(str(e))
    def close(self):
        self.save()
        for c in self.channels.values():c.stop.set()
        if all(c.disconnect() for c in self.channels.values()):self.root.destroy()
        else:messagebox.showwarning('Closing','TX still stopping; try again')

if __name__=='__main__':
    root=tk.Tk(); App(root); root.mainloop()
