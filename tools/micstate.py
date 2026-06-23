"""Print the default communications microphone mute state (0/1). Used to verify
the packaged exe's mic-toggle action actually works, without guessing."""
import comtypes
from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

comtypes.CoInitialize()
m = AudioUtilities.GetMicrophone()
v = cast(m.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
print(int(v.GetMute()))
