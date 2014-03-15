'''
Created on Oct 3, 2013

TODO: change chat window name when clicking on tab

@author: gaolong
'''


import pygtk
from encodings.base64_codec import base64_encode
pygtk.require('2.0')

import gtk
import gtk.glade
gtk.gdk.threads_init()



import gobject

import pango

import os
from os.path import dirname

from client.XMPP import XMPPClient, SQLLiteStorage
import ssl
import sleekxmpp

from nc.TreeParityMachine import TreeParityMachine, create_vector, TPMManager

import json

from Crypto.Cipher import AES
from Crypto import Random
import base64

import datetime

class TabLabel(gtk.Box):
    __gsignals__ = {
        "close-clicked": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }
    def __init__(self, label_text):
        gtk.Box.__init__(self)
        self.set_spacing(5) # spacing: [icon|5px|label|5px|close]  
        
        # icon
        self.icon = gtk.image_new_from_stock(gtk.STOCK_FILE, gtk.ICON_SIZE_MENU)
        self.pack_start(self.icon, False, False, 0)
        
        # label 
        label = gtk.Label(label_text)
        self.pack_start(label, True, True, 0)
        
        # close button
        button = gtk.Button()
        button.set_relief(gtk.RELIEF_NONE)
        button.set_focus_on_click(False)
        button.add(gtk.image_new_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU))
        button.connect("clicked", self.button_clicked)
        
        self.pack_start(button, False, False, 0)
        
        self.show_all()
    
    def button_clicked(self, button, data=None):
        self.emit("close-clicked")


class GLChatView:
    '''
    Contacts list window
    '''
        
    def __init__(self):
        '''
        Constructor
        '''
        # system vars
        
        self.CHAT_TYPE_OWNER = 1
        self.CHAT_TYPE_BUDDY = 2
        self.CHAT_TYPE_SYSTEM = 3
        
        self.client_activated = False
        
        self.storage = None
        self.account = None
        self.client = None
        
        self.predef_security_setups = {
            "Basic (AES-128)": {
                'k': 3,
                'n': 29,
                'l': 3
            },
            "Normal (AES-192)": {
                'k': 3,
                'n': 44,
                'l': 3
            },
            "Super (AES-256)": {
                'k': 3,
                'n': 58,
                'l': 3
            },
        }
        
        self.statuses = {
            "Available": "available",
            "Away": "away",
            "Free to chat": "chat",
            "Do not disturb": "dnd",
            "Not available": "xa",
        }
        
        self.sec_predef_store = gtk.ListStore(str)
        self.sec_predef_store.append(["Choose..."])
        for i in self.predef_security_setups:
            self.sec_predef_store.append([i])
            
        self.status_store = gtk.ListStore(str)
        for i in self.statuses:
            self.status_store.append([i])
        
        # self.local_sorage = LocalStorage()
        # self.local_users_data = []
        # self.contacts_tree = None
        
        self.users_treestore = gtk.TreeStore(int, gtk.gdk.Pixbuf, str)
        self.users_list = {}
        
        self.chat_elements = {}
        self.chats_opened = 0
                
        self.status_icons = {
            'available': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/available.png")),
            'away': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/away.png")),
            'chat': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/chat.png")),
            'dnd': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/dnd.png")),
            'error': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/error.png")),
            'probe': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/unavailable.png")),
            'subscribe': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/noauth.png")),
            'subscribed': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/noauth.png")),
            'unavailable': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/unavailable.png")),
            'unsubscribe': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/noauth.png")),
            'unsubscribed': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/noauth.png")),
            'xa': gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/roster/xa.png"))
        }
        
        self.icon_encrypted = gtk.gdk.pixbuf_new_from_file(os.path.join(dirname(__file__), "../resources/buttons/encrypted.png"))
        
        self.popupDialog = None
        
        # set the Glade file
        self.gladefile = os.path.join(dirname(__file__), "../resources/GLChat.glade")
        # init glade
        self.glade = gtk.Builder()
        self.glade.add_from_file(self.gladefile)
        self.glade.connect_signals(self)
        
        # window  
        self.window = self.glade.get_object("glWindow")
        self.chatWindow = self.glade.get_object("glChatWindow")
        self.secureWindow = self.glade.get_object("glSecureWindow")
        self.statusWindow = self.glade.get_object("glStatusWindow")
        self.addBuddyWindow = self.glade.get_object("glAddBuddyWindow")
        self.renameWindow = self.glade.get_object("glRenameWindow")
        self.authWindow = self.glade.get_object("glAuthWindow")
        self.historyWindow = self.glade.get_object("glHistoryWindow")
        
        if (self.window):
            self.window.connect("destroy", self.destroy)
            
        if (self.chatWindow):
            self.chatWindow.connect("destroy", self.chat_destroy)
            self.chatWindow.connect("delete-event", self.chat_delete)
            
        if (self.authWindow):
            self.authWindow.connect("destroy", self.auth_destroy)
         
        # users tree    
        self.users_tree = self.glade.get_object("glTreeview")
        
        if (self.users_tree):
            self.users_tree.set_headers_visible(False)
            self.users_tree.get_selection().set_mode(gtk.SELECTION_SINGLE)
            self.users_tree.connect("row-activated", self.user_activate_action, self)
            self.users_tree.connect("button_press_event", self.treeview_button_press_event)
        
        # menu
        
        self.treeviewPopup = gtk.Menu()
        menu_item0 = gtk.MenuItem("Rename")
        menu_item0.connect("activate", self.rename_from_list)
        self.treeviewPopup.append(menu_item0)
        menu_item = gtk.MenuItem("Subscribe")
        menu_item.connect("activate", self.subscribe_from_list)
        self.treeviewPopup.append(menu_item)
        menu_item2 = gtk.MenuItem("Unsubscribe")
        menu_item2.connect("activate", self.unsubscribe_from_list)
        self.treeviewPopup.append(menu_item2)
        menu_item3 = gtk.MenuItem("Delete")
        menu_item3.connect("activate", self.delete_from_list)
        self.treeviewPopup.append(menu_item3)
        menu_item4 = gtk.MenuItem("View history")
        menu_item4.connect("activate", self.history_from_list)
        self.treeviewPopup.append(menu_item4)
        self.treeviewPopup.show_all()
        
        
        self.chat_menu = self.glade.get_object("glMenubar1")
        
        accmenu = gtk.Menu()
        accel = gtk.MenuItem("Account")
        accel.set_submenu(accmenu)
        
        self.chat_menu.append(accel)
       
        statel = gtk.MenuItem("Change status")
        statel.connect("activate", self.menu_change_status)
        accmenu.append(statel)
        
        bdel = gtk.MenuItem("Add buddy")
        bdel.connect("activate", self.menu_add_buddy)
        accmenu.append(bdel)
        
        soel = gtk.MenuItem("Log Out")
        soel.connect("activate", self.menu_logout)
        accmenu.append(soel)
        
        self.chat_menu.append(accmenu)

        
        self.notebook = self.glade.get_object("glNotebook")
        
        # start secure window
        
        self.sec_predef_box = self.glade.get_object("predefCombobox")
        spb_cell = gtk.CellRendererText()
        self.sec_predef_box.pack_start(spb_cell)
        self.sec_predef_box.add_attribute(spb_cell, 'text', 0)
        self.sec_predef_box.set_model(self.sec_predef_store)
        self.sec_predef_box.set_active(0)
        
        self.sec_predef_box.connect('changed', self.predef_changed)
        
        self.sec_n_spin = self.glade.get_object("nSpinbutton")
        self.sec_n_spin.connect('value-changed', self.sec_val_changed)
        
        self.sec_k_spin = self.glade.get_object("kSpinbutton")
        self.sec_k_spin.connect('value-changed', self.sec_val_changed)
        
        self.sec_l_spin = self.glade.get_object("lSpinbutton")
        self.sec_l_spin.connect('value-changed', self.sec_val_changed)
        
        self.sec_info = self.glade.get_object("infoTextview")
        
        self.sec_ok_btn = self.glade.get_object("okButton")
        self.sec_ok_btn.connect('clicked', self.sec_ok_clicked)
        
        self.sec_cancel_btn = self.glade.get_object("cancelButton")
        self.sec_cancel_btn.connect('clicked', self.sec_cancel_clicked)
                
        # status window
        
        self.status_box = self.glade.get_object("statusCombobox")
        spb_cell = gtk.CellRendererText()
        self.status_box.pack_start(spb_cell)
        self.status_box.add_attribute(spb_cell, 'text', 0)
        self.status_box.set_model(self.status_store)
        self.status_box.set_active(0)
        
        self.status_entry = self.glade.get_object("statusEntry")
        
        self.status_cancel_btn = self.glade.get_object("statCancelButton")
        self.status_cancel_btn.connect('clicked', self.status_cancel_clicked)
        
        self.status_ok_btn = self.glade.get_object("statOkButton")
        self.status_ok_btn.connect('clicked', self.status_ok_clicked)
        
        # add buddy window
        
        self.ab_cancel_btn = self.glade.get_object("abCancelButton")
        self.ab_cancel_btn.connect('clicked', self.ab_cancel_clicked)
        
        self.ab_ok_btn = self.glade.get_object("abOkButton")
        self.ab_ok_btn.connect('clicked', self.ab_ok_clicked)
        
        self.ab_jid_entry = self.glade.get_object("jidEntry")
        
        # rename window
        
        self.rn_cancel_btn = self.glade.get_object("rnCancelButton")
        self.rn_cancel_btn.connect('clicked', self.rn_cancel_clicked)
        
        self.rn_ok_btn = self.glade.get_object("rnOkButton")
        self.rn_ok_btn.connect('clicked', self.rn_ok_clicked)
        
        self.rn_name_entry = self.glade.get_object("nameEntry")
        
        # auth window
        
        self.auth_cancel_btn = self.glade.get_object("authCancelButton")
        self.auth_cancel_btn.connect('clicked', self.auth_cancel_clicked)
        
        self.auth_ok_btn = self.glade.get_object("authOkButton")
        self.auth_ok_btn.connect('clicked', self.auth_ok_clicked)
        
        self.auth_check = self.glade.get_object("authCheckbutton")
        
        self.auth_jid_entry = self.glade.get_object("authJIDEntry")
        self.auth_pass_entry = self.glade.get_object("authPassEntry")
        
        # history window
        
        self.history_close_btn = self.glade.get_object("hCloseButton")
        self.history_close_btn.connect('clicked', self.history_close_clicked)
        
        self.history_clear_btn = self.glade.get_object("hClearButton")
        self.history_clear_btn.connect('clicked', self.history_clear_clicked)
        
        self.history_textview = self.glade.get_object("hTextview")
        
        # show window
        self.window.show_all()
        
    def treeview_button_press_event(self, widget, event):
        if event.button == 3:
            pthinfo = widget.get_path_at_pos(int(event.x), int(event.y))
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                widget.grab_focus()
                widget.set_cursor( path, col, 0)
                self.treeviewPopup.popup(None, None, None, event.button, event.time)
            return True
            
            
            #self.treeviewPopup.popup(None, None, None, event.button, event.time)
            #return True
        
    def unsubscribe_from_list(self, widget):
        model, iter = self.users_tree.get_selection().get_selected()
        i = self.users_treestore.get_value(iter, 0)
        
        self.client.unsubscribe_buddy(self.users_list[i]['jid'])
        
        #path = self.users_tree.get_path().get_ind
        
    def subscribe_from_list(self, widget):
        model, iter = self.users_tree.get_selection().get_selected()
        i = self.users_treestore.get_value(iter, 0)
        
        self.client.subscribe_buddy(self.users_list[i]['jid'])
        
    def delete_from_list(self, widget):
        model, iter = self.users_tree.get_selection().get_selected()
        i = self.users_treestore.get_value(iter, 0)
        
        self.client.remove_buddy(self.users_list[i]['jid'])
        
        self.users_treestore.remove(iter)
        del self.users_list[i]
        
    def rename_from_list(self, widget):
        model, iter = self.users_tree.get_selection().get_selected()
        i = self.users_treestore.get_value(iter, 0)
        
        self.renameWindow.set_title("Change name for {0}".format(self.users_list[i]['name']))
        self.rn_name_entry.set_text(self.users_list[i]['name'])
        self.renameWindow.show_all()
        
    def history_from_list(self, widget):
        model, iter = self.users_tree.get_selection().get_selected()
        i = self.users_treestore.get_value(iter, 0)
        
        self.historyWindow.set_title("History for {0}".format(self.users_list[i]['name']))
        
        history = self.storage.get_history(self.account['id'], self.users_list[i]['jid'])
        
        if history:
            buff = self.history_textview.get_buffer()
            
            b_tag = buff.create_tag("b", weight=pango.WEIGHT_BOLD)
            cgreen_tag = buff.create_tag("green", foreground="green")
            cblue_tag = buff.create_tag("blue", foreground="blue")
                        
            for el in history:
                fdate = datetime.datetime.fromtimestamp(el['date']).strftime('%Y-%m-%d %H:%M:%S')
                
                if el['is_account'] == 1:
                    buff.insert_with_tags(buff.get_end_iter(), "{0}".format(fdate), cgreen_tag)
                    buff.insert_with_tags(buff.get_end_iter(), " {0}:".format(self.account['jid']), b_tag, cgreen_tag)
                    buff.insert_with_tags(buff.get_end_iter(), " {0}\n".format(el['message']), cgreen_tag)
                else:
                    buff.insert_with_tags(buff.get_end_iter(), "{0}".format(fdate), cblue_tag)
                    buff.insert_with_tags(buff.get_end_iter(), " {0}:".format(self.users_list[i]['name']), b_tag, cblue_tag)
                    buff.insert_with_tags(buff.get_end_iter(), " {0}\n".format(el['message']), cblue_tag)
                
        self.historyWindow.show_all()
        
    def history_close_clicked(self, widget):
        
        self.historyWindow.set_title("")
        
        buf = self.history_textview.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        
        self.historyWindow.hide()
    
    def history_clear_clicked(self, widget):
        model, iter = self.users_tree.get_selection().get_selected()
        i = self.users_treestore.get_value(iter, 0)
        
        buf = self.history_textview.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        
        self.storage.clear_history(self.account['id'], self.users_list[i]['jid'])
        
    def start_client(self):
        if self.storage == None:
            self.storage = SQLLiteStorage()
        self.account = self.storage.get_account()
        
        print self.account
        
        if not self.account:
            print "show new account form"
            self.authWindow.show_all()
        else:
            self.client = XMPPClient(self.account['jid'], self.account['password'], self.storage, self.account['status'], self.account['status_message'])
            self.client.add_event_handler('changed_status', self.client_changed_status)
            self.client.add_event_handler("message", self.client_message_received)
            self.client.add_event_handler('sync_action', self.client_recv_sync)
            self.client.add_event_handler('confirm_sync_action', self.client_recv_confirm_sync)
            self.client.add_event_handler('change_mode_action', self.client_recv_change_mode)
            self.client.add_event_handler('subscription_finished', self.buddy_subscribed)
            self.client.add_event_handler('unsubscribe', self.buddy_unsubscribe)
            
            self.client.ssl_version = ssl.PROTOCOL_SSLv3
            if self.client.connect():
                self.client.process()
                
                self.init()
            else:
                print "False connection"
                return False
        return False
            
    def buddy_subscribed(self, presence):
        print "updating list"
        
        i = len(self.users_list)
        for jid in self.client.client_roster:
            
            print "testing jid: ", jid
            
            ni = self._get_user_i(jid)
            
            if ni is None:
                
                print "no jid"
                
                
                name = self.client.client_roster[jid]['name'] if self.client.client_roster[jid]['name'] != '' else jid 
                self.users_treestore.append(None, [i, self.status_icons['unavailable'], name])
            
                mgr = TPMManager()
                mgr.transport = self.client
            
                tpm = self.storage.get_tpm(jid)
                is_synced = False
            
                if tpm and mgr.fill(tpm['data']['k'], tpm['data']['n'], tpm['data']['l'], tpm['data']['w']):
                    is_synced = True

                self.users_list[i] = {'jid': jid, 'full': None, 'name': name, 'status': "", 'opened': False, 'pos': None, 'manager': mgr, 'is_synced': is_synced, 'is_secure': False}
                i += 1
                
        
        #self.users_tree.set_model(self.users_treestore)
    
    # status
    
    def buddy_unsubscribe(self, presence):
        print "unsubscribe"
        
        from_jid = sleekxmpp.JID(presence['from'])
        
        iter = self.users_treestore.get_iter_first()
        while iter != None:
            i = self.users_treestore.get_value(iter, 0)
            if self.users_list[i]['jid'] == from_jid.bare:
                self.users_treestore.set_value(iter, 1, self.status_icons['unsubscribed'])
                
                break
            iter = self.users_treestore.iter_next(iter)
    
    def menu_logout(self, widget):
        print "logout"
        self.client.disconnect()
        
        # clear all data
        
        self.users_list = {}
        
        print "clear, ",self.users_list
        
        self.chat_elements = {}
        self.chats_opened = 0
                
        pages_n = self.notebook.get_n_pages()
        for i in range(pages_n):
            self.notebook.remove_page(i)
        
        self.users_treestore.clear()
        
        
        
        self.chatWindow.hide()
        self.authWindow.show_all()
        
    def menu_change_status(self, widget):
        print "change status"
        self.statusWindow.show_all()
        
        # self.destroy()
        
    def status_cancel_clicked(self, widget):
        self.statusWindow.hide()
        self.status_box.set_active(0)
        self.status_entry.set_text('')
        
    def status_ok_clicked(self, widget):
        act = self.status_box.get_active_text()
        if act in self.statuses:
            status = self.statuses[act]
            status_txt = self.status_entry.get_text()
            self.client.send_presence(pshow=status, pstatus=status_txt)
            self.storage.set_status(self.account['id'], status, status_txt)
            
        self.statusWindow.hide()
        self.status_box.set_active(0)
        self.status_entry.set_text('')
        
    # add buddy
        
    def menu_add_buddy(self, widget):
        print "add buddy"
        self.addBuddyWindow.show_all()
        
        
    def ab_cancel_clicked(self, widget):
        self.addBuddyWindow.hide()
        self.ab_jid_entry.set_text('')
        
    def ab_ok_clicked(self, widget):
        jid = self.ab_jid_entry.get_text()
        
        if len(jid) > 0:
            self.client.subscribe_buddy(jid)
                    
        self.addBuddyWindow.hide()
        self.ab_jid_entry.set_text('')
        
    def auth_cancel_clicked(self, widget):
        
        gtk.main_quit()
        
    def auth_ok_clicked(self, widget):
        
        jid = self.auth_jid_entry.get_text()
        passwd = self.auth_pass_entry.get_text()
        auto_conn = self.auth_check.get_active()
        
        self.authWindow.hide()
        self.auth_jid_entry.set_text("")
        self.auth_pass_entry.set_text("")
        self.auth_check.set_active(False)
        
        chk_acc = self.storage.get_account_by_JID(jid)
                
        if chk_acc:
            acc_auto_conn = True if chk_acc['auto_connect'] else False
            if auto_conn != acc_auto_conn:
                self.storage.change_account_data(chk_acc['id'], passwd, auto_conn)
        else:
            if auto_conn:
                self.storage.disable_all_auto_conn()
            self.storage.add_account(jid, passwd, auto_conn)
            
        self.start_client()
                
    def client_changed_status(self, event):
        print "status changed"
        
        from_jid = sleekxmpp.JID(event['from'])
        
        print from_jid.bare, "-", event['status'], " - ", event['type']
        
        iter = self.users_treestore.get_iter_first()
        while iter != None:
            i = self.users_treestore.get_value(iter, 0)
            if self.users_list[i]['jid'] == from_jid.bare:
                
                self.users_list[i]['full'] = from_jid
                self.users_list[i]['manager'].recvr = from_jid
                
                self.users_treestore.set_value(iter, 1, self.status_icons[event['type']])
                
                self.users_list[i]['status'] = event['status']
                
                if event['status'] != '':
                    self.users_treestore.set_value(iter, 2, "{0} ({1})".format(self.users_list[i]['name'], event['status']))
                break
            iter = self.users_treestore.iter_next(iter)
            
    def rn_cancel_clicked(self, widget):
        self.renameWindow.hide()
        self.rn_name_entry.set_text('')
        
    def rn_ok_clicked(self, widget):
        name = self.rn_name_entry.get_text()
        
        if len(name) > 0:
            model, iter = self.users_tree.get_selection().get_selected()
            i = self.users_treestore.get_value(iter, 0)
            self.client.rename_buddy(self.users_list[i]['jid'], name)
            
            self.users_list[i]['name'] = name
            self.client.client_roster[self.users_list[i]['jid']]
            self.users_treestore.set_value(iter, 2, "{0} ({1})".format(name, self.users_list[i]['status']))
            
                    
        self.renameWindow.hide()
        self.rn_name_entry.set_text('')
            
            
    def client_message_received(self, event):
        from_jid = sleekxmpp.JID(event['from'])
        i = self._get_user_i(from_jid.bare)
        
        if i == None:
            return
        if not self.users_list[i]['opened']:
            self._add_tab(i)
        
        r_msg = event['body']
        if self.users_list[i]['is_secure']:
            r_msg = self.__decode(r_msg, self.users_list[i]['manager'].get_key())
        
        self._print_message(i, self.users_list[i]['name'], r_msg, self.CHAT_TYPE_BUDDY, self.users_list[i]['is_secure'])
        
        self.storage.add_history(self.account['id'], from_jid.bare, r_msg, False)
                    
    def client_recv_sync(self, iq):
        print "RECV"
        i = self._get_user_i(iq['from'].bare)
        if i == None:
            return
        
        status = iq['sync']['status']
        
        if status == "fail":
            print "FAIL"
            
            it = json.loads(iq['sync']['it'])
            if not it:
                self.client.tpm_send(iq['from'], status="fail", it=1)
                
            self._print_message(i, "System", "Sync failed. Try again.")
            
        elif status == "success":
            print "Success"
            
            it = json.loads(iq['sync']['it'])
            if not it:
                self.client.tpm_send(iq['from'], status="success", it = 1)
            
            data = self.users_list[i]['manager'].get_data()
            
            self.storage.set_tpm(self.account['id'], iq['from'].bare, data, True)
            
            self.users_list[i]['is_synced'] = True
            
            self._print_message(i, "System", "Sync finished successfully.")
            
        else:
            rvec = json.loads(iq['sync']['rvec'])
            out = json.loads(iq['sync']['out'])
            oout = None
            if iq['sync']['oout']:
                oout = json.loads(iq['sync']['oout'])
            w = iq['sync']['w']
            eqout = json.loads(iq['sync']['eqout'])
        
            it = json.loads(iq['sync']['it'])
        
            self.users_list[i]['manager'].recv(rvec, oout, out, w, eqout, status, it)
            
    def client_recv_confirm_sync(self, iq):
        print "CONFIRM RECV"
        
        i = self._get_user_i(iq['from'].bare)
        if i == None:
            return
                
        status = iq['confirmsync']['status']
        
        print status
        
        k = int(iq['confirmsync']['k'])
        n = int(iq['confirmsync']['n'])
        l = int(iq['confirmsync']['l'])
        
        if status == "confirm_secure":
            
            print "confirm received ",k,n,l
            
            self._print_message(i, "System", "Sync request received. k={0}, n={1}, l={2}".format(k,n,l))
            
            gobject.idle_add(self.show_sync_confirm_dlg, i, iq['from'], k, n, l)
            
        elif status == "secure_confirmed":
            self._print_message(i, "System", "Sync confirmed. Start sync.")
            
            gobject.idle_add(self.start_secure_connection, i, k, n, l)
            
        elif status == "secure_rejected":
            self._print_message(i, "System", "Sync rejected.")
            
    def client_recv_change_mode(self, iq):
        print "CMODE RECV"
        
        i = self._get_user_i(iq['from'].bare)
        if i == None:
            return
        
        key = iq['changemode']['key']
        val = json.loads(iq['changemode']['val'])
        
        if key == "secure":
            self.users_list[i]['is_secure'] = val
            if val:
                self._print_message(i, "System", "Encryption enabled.")
            else:
                self._print_message(i, "System", "Encryption disabled.")
        
    def show_sync_confirm_dlg(self, i, recv, k, n, l):
        gtk.gdk.threads_enter()
        
        messagedialog = gtk.MessageDialog(self.chatWindow, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, "Sync with {0}?\n k={1}, n={2}, l={3}".format(recv.bare, k, n, l))
        messagedialog.set_title("Sync confirmation")
        resp = messagedialog.run()
        messagedialog.destroy()
        
        if resp == gtk.RESPONSE_YES:
            self.users_list[i]['manager'].init(k, n, l)
            self.client.tpm_confirm_send(recv, "secure_confirmed", k, n, l)
            
        elif resp == gtk.RESPONSE_NO:
            self.client.tpm_confirm_send(recv, "secure_rejected", k, n, l)
                    
        gtk.gdk.threads_leave()

    def _get_user_i(self, jid):
        for i in self.users_list:
            if self.users_list[i]['jid'] == jid:
                return i
        return None
    
    def _get_user_i_by_pos(self, pos):
        for i in self.users_list:
            if self.users_list[i]['pos'] == pos:
                return i
        return None
    
    def init(self):
        print "INIT"
        i = 0
        for jid in self.client.client_roster:
            name = self.client.client_roster[jid]['name'] if self.client.client_roster[jid]['name'] != '' else jid 
            self.users_treestore.append(None, [i, self.status_icons['unavailable'], name])
            
            mgr = TPMManager()
            mgr.transport = self.client
            
            tpm = self.storage.get_tpm(jid)
            is_synced = False
            
            if tpm and mgr.fill(tpm['data']['k'], tpm['data']['n'], tpm['data']['l'], tpm['data']['w']):
                is_synced = True
            
            self.users_list[i] = {'jid': jid, 'full': None, 'name': name, 'status': "", 'opened': False, 'pos': None, 'manager': mgr, 'is_synced': is_synced, 'is_secure': False}
            i += 1
        
        if not self.client_activated:
            self.users_tree.set_model(self.users_treestore)
        
            # status
            cell = gtk.CellRendererPixbuf()
            columnS = gtk.TreeViewColumn('S', cell)
            columnS.add_attribute(cell, 'pixbuf', 1)
            self.users_tree.append_column(columnS)
        
            # name
            cell = gtk.CellRendererText()
            columnTitle = gtk.TreeViewColumn('Title', cell)
            columnTitle.add_attribute(cell, 'text', 2)
            self.users_tree.append_column(columnTitle)
        
            self.client_activated = True
        
    def predef_changed(self, entry):
        act = entry.get_active_text()
        if act in self.predef_security_setups:
            self.sec_n_spin.set_value(self.predef_security_setups[act]['n'])
            self.sec_k_spin.set_value(self.predef_security_setups[act]['k'])
            self.sec_l_spin.set_value(self.predef_security_setups[act]['l'])
            self._show_secure_info()
            
    def sec_val_changed(self, button):
        self._show_secure_info()
        
    def sec_ok_clicked(self, button):
        print "OK"
        
        self.secureWindow.hide()
        
        print "hidden"
        
        pos = self.notebook.get_current_page()
        i = self._get_user_i_by_pos(pos)
        
        n = self.sec_n_spin.get_value_as_int()
        k = self.sec_k_spin.get_value_as_int()
        l = self.sec_l_spin.get_value_as_int()
        
        
        
        self._print_message(i, "System", "Waiting for confirmation...")
        
        self._send_sec_confirmation(i, k, n, l)
        
        print "end"
        
        #self.start_secure_connection(i, k, n, l)
        
    def close_waiting_popup(self, widget):
        print "close called"
        
    def _send_sec_confirmation(self, i, k, n, l):
        self.client.tpm_confirm_send(self.users_list[i]['full'], "confirm_secure", k, n, l)    
        
    def sec_cancel_clicked(self, button):
        print "CANCEL"
        self.secureWindow.hide()
        
    def _show_secure_info(self):
        k = self.sec_k_spin.get_value_as_int()
        n = self.sec_n_spin.get_value_as_int()
        l = self.sec_l_spin.get_value_as_int()
        
        buf = self.sec_info.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        
        key_size = 37 / float(2 * l + 1)
        
        buf.insert(buf.get_end_iter(), "Key length: {0}\n".format(int(k * n / key_size)))
        buf.insert(buf.get_end_iter(), "Key variants: {0}^{1}\n".format(2*l+1, k*n))
        
        
    def user_activate_action(self, treeview, path, view_column, user_data):
        '''
            Double click on item
        '''
        print "user_activate_action"
        
        iter = self.users_treestore.get_iter(path)
        i = self.users_treestore.get_value(iter, 0)

        self._add_tab(i)
        
    def close_tab_clicked(self, tab_label, notebook, tab_widget):
        print "close tab"
                
        num = self.notebook.page_num(tab_widget)
        self.chats_opened -= 1
        
        if num < self.chats_opened:
            for i in self.users_list:
                if self.users_list[i]['opened'] and self.users_list[i]['pos'] > num:
                    self.users_list[i]['pos'] -= 1
                elif self.users_list[i]['pos'] == num:
                    del self.chat_elements[i]
                    self.users_list[i]['opened'] = False
                    self.users_list[i]['pos'] = None
        else:
            for i in self.users_list:
                if self.users_list[i]['pos'] == num:
                    del self.chat_elements[i]
                    self.users_list[i]['opened'] = False
                    self.users_list[i]['pos'] = None
                    break
        
        self.notebook.remove_page(num)
        
    def send_message(self, i):
        msg = self.chat_elements[i]['inp'].get_text()
        
        if msg != '':
            s_msg = msg
            if self.users_list[i]['is_secure']:
                s_msg = self.__encode(s_msg, self.users_list[i]['manager'].get_key())
                print "sending; ", s_msg
            
            self.client.send_message(mto=self.users_list[i]['jid'], mbody=s_msg, mtype='chat')
            self._print_message(i, self.account['jid'], msg, self.CHAT_TYPE_OWNER, self.users_list[i]['is_secure'])
            self.chat_elements[i]['inp'].set_text('')
            
            self.storage.add_history(self.account['id'], self.users_list[i]['jid'], msg, True)
           
    def _print_message(self, i, sender, message, type=None, encrypted=False):
        buff = self.chat_elements[i]['tview'].get_buffer()
        
        b_tag = buff.get_tag_table().lookup("b")
        cred_tag = buff.get_tag_table().lookup("red")
        cblue_tag = buff.get_tag_table().lookup("blue")
        cgreen_tag = buff.get_tag_table().lookup("green")
        
        if encrypted and (type == self.CHAT_TYPE_OWNER or type == self.CHAT_TYPE_BUDDY):
            print "enc"
            buff.insert_pixbuf(buff.get_end_iter(), self.icon_encrypted)
        
        if type == self.CHAT_TYPE_OWNER:
            buff.insert_with_tags(buff.get_end_iter(), "{0}:".format(sender), b_tag, cgreen_tag)
            buff.insert_with_tags(buff.get_end_iter(), " {0}\n".format(message), cgreen_tag)
        elif type == self.CHAT_TYPE_BUDDY:
            buff.insert_with_tags(buff.get_end_iter(), "{0}:".format(sender), b_tag, cblue_tag)
            buff.insert_with_tags(buff.get_end_iter(), " {0}\n".format(message), cblue_tag)
        else:
            buff.insert_with_tags(buff.get_end_iter(), "{0}:".format(sender), b_tag, cred_tag)
            buff.insert_with_tags(buff.get_end_iter(), " {0}\n".format(message), cred_tag)
        
    def _add_tab(self, i):
        '''
        Add new chat tab and open chat window
        '''
        if self.users_list[i]['opened']:
            self.notebook.set_current_page(self.users_list[i]['pos'])
            self.chatWindow.show_all()
            return
               
        if i not in self.chat_elements:
            self.chat_elements[i] = {'swin': None, 'tview': None, 'inp': None, 'submit': None, 'enc_btn': None}
            
        cont_box = gtk.VBox()
        
        
        toolbar = gtk.Toolbar()
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_BOTH)
        toolbar.set_icon_size(gtk.ICON_SIZE_MENU)
                
        iconw = gtk.Image() # icon widget
        iconw.set_from_file(os.path.join(dirname(__file__), "../resources/buttons/lock_closed32.png"))
        
        sec_button = gtk.Button()
        sec_button.connect("button-press-event", self.secure_clicked, {'i': i})
        sec_button.set_image(iconw)
        
        toolbar.append_element(
            gtk.TOOLBAR_CHILD_WIDGET,
            sec_button,
            None,
            "Toggle secure chatting",
            "Private",
            None,
            None,
            None)
        toolbar.append_space()
        # tooltips_button.set_active(True)
        
        cont_box.pack_start(toolbar, False, True, 0)
        
        self.chat_elements[i]['swin'] = gtk.ScrolledWindow()
        self.chat_elements[i]['swin'].set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        
        self.chat_elements[i]['tview'] = gtk.TextView()
        self.chat_elements[i]['tview'].set_wrap_mode(gtk.WRAP_WORD)
        self.chat_elements[i]['tview'].set_editable(False)
        
        buff = self.chat_elements[i]['tview'].get_buffer()
        b_tag = buff.create_tag("b", weight=pango.WEIGHT_BOLD)
        cred_tag = buff.create_tag("red", foreground="red")
        cgreen_tag = buff.create_tag("green", foreground="green")
        cblue_tag = buff.create_tag("blue", foreground="blue")
        
        self.chat_elements[i]['swin'].add(self.chat_elements[i]['tview'])
                
        cont_box.pack_start(self.chat_elements[i]['swin'], True, True, 1)
                
        subcont_box = gtk.HBox()
        
        self.chat_elements[i]['inp'] = gtk.Entry()
        self.chat_elements[i]['inp'].connect("key-press-event", self.input_key_pressed, {'i': i})
        
        
        subcont_box.pack_start(self.chat_elements[i]['inp'], True, True, 0)
        
        self.chat_elements[i]['submit'] = gtk.Button(label="Send")
        self.chat_elements[i]['submit'].connect("clicked", self.send_message_clicked, {'i': i})
        
        subcont_box.pack_start(self.chat_elements[i]['submit'], False, True, 1)
        
        cont_box.pack_start(subcont_box, False, True, 2)
        
        
        tab_label = TabLabel(self.users_list[i]['name'])
        tab_label.connect("close-clicked", self.close_tab_clicked, self.notebook, cont_box)
        self.notebook.append_page(cont_box, tab_label)
        
        self.users_list[i]['opened'] = True
        self.users_list[i]['pos'] = self.chats_opened
        self.chats_opened += 1
        
        self.chatWindow.show_all()
        
        
    def secure_clicked(self, widget, event, user_data):
        menu = gtk.Menu()
        
        menuitem1 = gtk.MenuItem("Sync with buddy") # Sync with buddy / Remove sync
        menuitem1.connect("activate", self.toggle_sync, user_data)
        menuitem2 = gtk.MenuItem("Toggle encryption") # Begin secure conversation
        menuitem2.connect("activate", self.toggle_encryption, user_data)
        menuitem3 = gtk.MenuItem("Show security status") # print status
        menuitem3.connect("activate", self.show_security_status, user_data)
        
        menu.append(menuitem1)
        menu.append(menuitem2)
        menu.append(menuitem3)
        
        menu.attach_to_widget(widget, self.sec_menu_detach)
        
        menu.show_all()
        
        menu.popup(None, None, None, event.button, event.time)

    def toggle_sync(self, widget, user_data):
        print "toggle_sync ", user_data
        
        is_synced = self.users_list[user_data['i']]['is_synced']
        
        if not is_synced:
            self.secureWindow.show_all()
        else:
            messagedialog = gtk.MessageDialog(self.chatWindow, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, "You have already synced with {0}. Delete sync?".format(self.users_list[user_data['i']]['name']))
            messagedialog.set_title("Delete sync?")
            resp = messagedialog.run()
            messagedialog.destroy()
        
            if resp == gtk.RESPONSE_YES:
                self.terminate_secure_connection(user_data['i'])
        
        
    def toggle_encryption(self, widget, user_data):
        print "toggle_encryption ", user_data
        i = user_data['i']
        
        if self.users_list[i]['is_secure']:
            self.users_list[i]['is_secure'] = False
            self.client.change_mode_send(self.users_list[i]['full'], "secure", False)
            self._print_message(i, "System", "Encryption disabled.")
        else:
            self.users_list[i]['is_secure'] = True
            self.client.change_mode_send(self.users_list[i]['full'], "secure", True)
            self._print_message(i, "System", "Encryption enabled.")
        
    def show_security_status(self, widget, user_data):
        i = user_data['i']
        
        if self.users_list[i]['is_synced']:
            mgr = self.users_list[i]['manager']
            
            self._print_message(i, "System", "Synchronized. k={0}, n={1}, l={2}".format(mgr.k, mgr.n, mgr.l))
        else:
            self._print_message(i, "System", "Not synchronized.")
            
        if self.users_list[i]['is_secure']:
            self._print_message(i, "System", "Encryption enabled.")
        else:
            self._print_message(i, "System", "Encryption disabled.")
        
        
    def sec_menu_detach(self, item):
        print "detach"
        
        
    '''def toggle_secure(self, widget, user_data):
        print "toggle ", widget.get_active()
        
        if widget.get_active():
            self.start_secure_connection(user_data['i'])
        else:
            self.terminate_secure_connection(user_data['i'])'''
        
    def send_message_clicked(self, button, user_data):
        print "send clicked"
        self.send_message(user_data['i'])
        
    def input_key_pressed(self, entry, event, user_data):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            self.send_message(user_data['i'])
    
    def destroy(self, widget, data=None):
        print "destroy"
        self.client.disconnect()
        gtk.main_quit()

    def auth_destroy(self, widget, data=None):
        print "destroy"
        gtk.main_quit()


    def chat_delete(self, widget, event, data=None):
        print "delete chat"
        widget.hide()
        return True

    def chat_destroy(self, widget, data=None):
        print "close chat"
        
    def main(self):
        gtk.gdk.threads_init()
        gtk.main()
        
        
    def start_secure_connection(self, i, k, n, l):
        gtk.gdk.threads_enter()
        
        print "begin secure"
        
        
        #input = create_vector(3, 5)
        #output = -1
        #self.client.send_sync(self.users_list[i]['full'], input, output)
        
        
        self.users_list[i]['manager'].init(k, n, l)
        self.users_list[i]['manager'].start_iter()
        
        gtk.gdk.threads_leave()
        
    def terminate_secure_connection(self, i):
        self.users_list[i]['manager'].clear()
        self.users_list[i]['is_synced'] = False
        
        self.storage.remove_tpm(self.account['id'], self.users_list[i]['jid'])
        
        self._print_message(i, "System", "Synchronization removed.")
        
        if self.users_list[i]['is_secure']:
            self.users_list[i]['is_secure'] = False
            self.client.change_mode_send(self.users_list[i]['full'], "secure", False)
            self._print_message(i, "System", "Encryption disabled.")
    
    def __get_aes_key(self, key):
        en_key = key
        key_len = len(key)
        if key_len != 16 and key_len != 24 and key_len != 32:
            if key_len > 32:
                en_key = key[:32]
            elif key_len < 16:
                en_key = key.ljust(16)
            elif key_len < 24:
                en_key = key.ljust(24)
            elif key_len < 32:
                en_key = key.ljust(32)
        return en_key
        
    def __encode(self, msg, key):
        en_key = self.__get_aes_key(key)

        iv = Random.new().read(AES.block_size)
        
        obj = AES.new(en_key, AES.MODE_CFB, iv)
        
        res = iv + obj.encrypt(msg)
        
        return base64.b64encode(res)
    
    def __decode(self, msg, key):
        de_key = self.__get_aes_key(key)
        
        msg = base64.b64decode(msg)
        
        obj = AES.new(de_key, AES.MODE_CFB, msg[:AES.block_size])
        
        return obj.decrypt(msg[AES.block_size:])
        
        
        
        
        
        
        
        
        