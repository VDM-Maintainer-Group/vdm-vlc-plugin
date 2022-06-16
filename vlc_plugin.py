#!/usr/bin/env python3
import os, time, json, dbus
import subprocess as sp
from pathlib import Path
from pyvdm.interface import CapabilityLibrary, SRC_API

DBG = 1
SLOT = 0.40
PROG_NAME = 'vlc'

SET_PLAYBACK = {
    'Stopped': lambda x: x.Stop(),
    'Paused':  lambda x: x.Pause(),
    'Playing': lambda x: x.Play()
}

class VLCPlugin(SRC_API):
    def _gather_record(self):
        sess = dbus.SessionBus()
        dbus_iface = dbus.Interface(sess.get_object('org.freedesktop.DBus', '/'),
                    dbus_interface='org.freedesktop.DBus')
        
        record = dict()

        try:
            sess.list_names().index('org.mpris.MediaPlayer2.vlc')
        except:
            pass
        else:
            _pid = dbus_iface.GetConnectionUnixProcessID('org.mpris.MediaPlayer2.vlc')
            _window = self.xm.get_windows_by_pid(_pid)[0]
            ##
            _obj = sess.get_object('org.mpris.MediaPlayer2.vlc', '/org/mpris/MediaPlayer2')
            props_iface  = dbus.Interface(_obj, 'org.freedesktop.DBus.Properties')
            player_iface = dbus.Interface(_obj, 'org.mpris.MediaPlayer2.Player')
            player_props = lambda x: props_iface.Get('org.mpris.MediaPlayer2.Player', x)
            tracks_iface = dbus.Interface(_obj, 'org.mpris.MediaPlayer2.TrackList')
            tracks_props = lambda x: props_iface.Get('org.mpris.MediaPlayer2.TrackList', x)

            _metadata = tracks_iface.GetTracksMetadata( tracks_props('Tracks') )
            record = {
                'tracks_uri': [ x['xesam:url'] for x in _metadata ],
                'current_uri':  player_props('Metadata')['xesam:url'],
                'position':       player_props('Position'),
                'play_status':    player_props('PlaybackStatus'),
                'volume':         player_props('Volume'),
                'loop_status':    player_props('LoopStatus'),
                'shuffle_status': player_props('Shuffle'),
                'window': {
                    'desktop': _window['desktop'],
                    'states':  _window['states'],
                    'xyhw':    _window['xyhw']
                }
            }

        return record

    def _resume_status(self, record):
        sess = dbus.SessionBus()
        dbus_iface = dbus.Interface(sess.get_object('org.freedesktop.DBus', '/'),
                    dbus_interface='org.freedesktop.DBus')
        
        try:
            sess.list_names().index('org.mpris.MediaPlayer2.vlc')
        except:
            sp.Popen(['vlc'], start_new_session=True)
            time.sleep(2*SLOT)

        ## resume window status
        _pid = dbus_iface.GetConnectionUnixProcessID('org.mpris.MediaPlayer2.vlc')
        _window = self.xm.get_windows_by_pid(_pid)[0]
        s = record['window']
        self.xm.set_window_by_xid(_window['xid'], s['desktop'], s['states'], s['xyhw'])

        ## resume content status
        _obj = sess.get_object('org.mpris.MediaPlayer2.vlc', '/org/mpris/MediaPlayer2')
        props_iface  = dbus.Interface(_obj, 'org.freedesktop.DBus.Properties')
        player_iface = dbus.Interface(_obj, 'org.mpris.MediaPlayer2.Player')
        tracks_iface = dbus.Interface(_obj, 'org.mpris.MediaPlayer2.TrackList')
        player_set = lambda k,v: props_iface.Set('org.mpris.MediaPlayer2.Player', k,v)
        tracks_get = lambda x: props_iface.Get('org.mpris.MediaPlayer2.TrackList', x)
        ## resume track metadata
        for _track in record['tracks_uri'][::-1]:
            _current = True if _track==record['current_uri'] else False
            tracks_iface.AddTrack(_track, '/org/mpris/MediaPlayer2/TrackList/NoTrack', _current)
        player_iface.Play(); time.sleep(SLOT)
        ## resume player status
        player_set('Shuffle',    record['shuffle_status'])
        player_set('LoopStatus', record['loop_status'])
        player_set('Volume',     record['volume'])
        _metadata = tracks_iface.GetTracksMetadata( tracks_get('Tracks') )
        player_iface.Seek( record['position'] )
        ## resume playback status
        SET_PLAYBACK[ record['play_status'] ]( player_iface )
        
        pass

    def onStart(self):
        self.xm = CapabilityLibrary.CapabilityHandleLocal('x11-manager')
        return 0

    def onStop(self):
        return 0

    def onSave(self, stat_file):
        ## gathering record
        record = self._gather_record()
        ## write to file
        with open(stat_file, 'w') as f:
            json.dump(record, f)
            pass
        return 0

    def onResume(self, stat_file):
        ## load stat file with failure check
        with open(stat_file, 'r') as f:
            _file = f.read().strip()
        if len(_file)==0:
            return 0
        else:
            try:
                record = json.loads(_file)
            except:
                return -1
        ## rearrange windows by title
        self._resume_status(record)
        return 0

    def onClose(self):
        ## force close all
        os.system( f'killall {PROG_NAME}' )
        return 0
    pass

if __name__ == '__main__':
    _plugin = VLCPlugin()
    _plugin.onStart()

    ## gathering record
    record = _plugin._gather_record()
    print( json.dumps(record, indent=4) )
    _plugin.onClose()

    ## test resume
    time.sleep( 2.0 )
    _plugin._resume_status(record)
    pass
