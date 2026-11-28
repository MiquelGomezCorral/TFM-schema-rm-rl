| Step | Labels true | State | Pay | Total | What happens |
|---|---|---|---|---|---|
| 1 | none | u0 -> u0 | 0 | 0 | the shop is quiet, nothing happens |
| 2 | `siren_ringing` | u0 -> u1 | -1 | -1 | the siren starts ringing: the promise opens |
| 3 | `siren_ringing` | u1 -> u1 | 0 | -1 | the agent walks to the switch, the siren still rings |
| 4 | `switch_toggled` | u1 -> u0 | +1 | 0 | the agent toggles the switch, the siren stops: the promise is kept |
| 5 | `siren_ringing` | u0 -> u1 | -1 | -1 | the siren rings again: the promise opens |
| 6 | `switch_toggled` | u1 -> u0 | +1 | 0 | the agent toggles the switch again: the promise is kept |
