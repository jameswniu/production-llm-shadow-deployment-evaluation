# Every verdict, all 130 incidents

This table checks, incident by incident, whether the challenger (GLM-5.3, given the same logs) classes a failed scheduled job the way the medic (the trusted Claude agent) did, so a reader can count the matches and misses behind every number on the main page.

Medic class is the trusted model's call, Challenger class is the candidate's, Stage is the letter of the scheduled job that failed (D, E and F are avatar video renders, the render family; the rest are automation, the ops family), Split says whether the incident was held out of tuning, and Logs says whether its logs ship or stay private with only these fields and a hash.

Each row is one frozen incident: the class the trusted model logged, the class the challenger gave from the same logs, and whether the two agree. A withheld incident ships only these fields plus a hash of its private original, never its logs.

| Incident | Family | Stage | Split | Medic class | Challenger class | Result | Logs |
|---|---|---|---|---|---|---|---|
| 5-20260816T0806 | ops | 5 | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| I-20260905T0250 | ops | I | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| L-20260823T1624 | ops | L | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| L-20260826T1837 | ops | L | dev | JUDGMENT | JUDGMENT | MATCH | withheld |
| L-20260827T1153 | ops | L | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| L-20261031T0913 | ops | L | holdout | MECHANICAL | - | PENDING | withheld |
| M-20260814T1340 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260815T2019 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260822T1401 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260823T1151 | ops | M | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260823T2029 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260827T1153 | ops | M | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260902T0916 | ops | M | holdout | MECHANICAL | JUDGMENT | MISS | withheld |
| M-20260903T1000 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260905T0303 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260907T0044 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260912T2142 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260913T0745 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260918T1555 | ops | M | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| M-20260919T1557 | ops | M | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| M-20260927T1756 | ops | M | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| M-20261031T2012 | ops | M | holdout | JUDGMENT | - | PENDING | withheld |
| N-20260823T1209 | ops | N | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| N-20260830T0928 | ops | N | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| N-20260913T1024 | ops | N | holdout | MECHANICAL | JUDGMENT | MISS | withheld |
| O-20260918T2140 | ops | O | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| O-20260919T2032 | ops | O | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| O-20260920T1530 | ops | O | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| O-20260921T0235 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20260922T0837 | ops | O | holdout | MECHANICAL | JUDGMENT | MISS | withheld |
| O-20260923T1611 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20260929T1057 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261002T1243 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261004T1801 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261005T0034 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261007T0941 | ops | O | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| O-20261008T0827 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261012T0731 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261014T0816 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261020T0816 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261022T0848 | ops | O | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| O-20261026T1210 | ops | O | holdout | JUDGMENT | - | PENDING | withheld |
| P-20260915T0101 | ops | P | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| P-20260921T0317 | ops | P | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| P-20261002T0008 | ops | P | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| P-20261007T1516 | ops | P | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| Q-20260818T1802 | ops | Q | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| Q-20260826T2327 | ops | Q | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| Q-20260827T0040 | ops | Q | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| Q-20260829T0647 | ops | Q | dev | JUDGMENT | JUDGMENT | MATCH | withheld |
| Q-20260829T0705 | ops | Q | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| Q-20260902T0246 | ops | Q | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| Q-20260904T0408 | ops | Q | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| Q-20260906T0453 | ops | Q | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| Q-20260920T1904 | ops | Q | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| Q-20261103T2314 | ops | Q | holdout | JUDGMENT | - | PENDING | withheld |
| Q-20261108T0255 | ops | Q | holdout | MECHANICAL | - | PENDING | withheld |
| S-20260825T0151 | ops | S | dev | JUDGMENT | MECHANICAL | MISS | withheld |
| S-20260826T1837 | ops | S | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| S-20260827T1940 | ops | S | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| S-20260830T0546 | ops | S | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| S-20260902T0557 | ops | S | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| S-20260903T0110 | ops | S | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| S-20260905T1652 | ops | S | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| S-20260915T0030 | ops | S | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| S-20260922T0100 | ops | S | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| S-20260927T0101 | ops | S | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| S-20261001T0313 | ops | S | holdout | MECHANICAL | JUDGMENT | MISS | withheld |
| T-20260828T1636 | ops | T | dev | MECHANICAL | MECHANICAL | MATCH | withheld |
| T-20260830T2139 | ops | T | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| T-20260921T1005 | ops | T | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| U-20260829T0129 | ops | U | dev | JUDGMENT | JUDGMENT | MATCH | withheld |
| U-20260903T1025 | ops | U | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| W-20260902T0952 | ops | W | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| W-20260910T1724 | ops | W | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| W-20260911T0913 | ops | W | holdout | MECHANICAL | JUDGMENT | MISS | withheld |
| W-20260913T1650 | ops | W | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| W-20260914T2045 | ops | W | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| W-20260917T1344 | ops | W | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| W-20260921T1005 | ops | W | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| W-20261104T1506 | ops | W | holdout | JUDGMENT | - | PENDING | withheld |
| W-20261105T2100 | ops | W | holdout | MECHANICAL | - | PENDING | withheld |
| XXIII-20261103T2206 | ops | XXIII | holdout | MECHANICAL | - | PENDING | withheld |
| q-followup-20260828 | ops | Q | dev | JUDGMENT | JUDGMENT | MATCH | withheld |
| D-20260814T0730 | render | D | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| D-20260902T0916 | render | D | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| D-20260903T0946 | render | D | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| D-20260904T2134 | render | D | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| D-20260905T0241 | render | D | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| D-20260908T0724 | render | D | holdout | MECHANICAL | JUDGMENT | MISS | withheld |
| D-20260918T1509 | render | D | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| D-20260920T0821 | render | D | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| D-20260926T0737 | render | D | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| D-20260928T0923 | render | D | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| D-20261020T0752 | render | D | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| D-20261106T0118 | render | D | holdout | JUDGMENT | - | PENDING | withheld |
| D-20261108T0809 | render | D | holdout | MECHANICAL | - | PENDING | withheld |
| D-20261109T1103 | render | D | holdout | JUDGMENT | - | PENDING | withheld |
| E-20260908T0825 | render | E | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| E-20260911T2058 | render | E | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| F-20260814T1816 | render | F | holdout | JUDGMENT | MECHANICAL | MISS | shipped |
| F-20260815T2145 | render | F | holdout | JUDGMENT | MECHANICAL | MISS | shipped |
| F-20260816T1805 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | shipped |
| F-20260817T0004 | render | F | holdout | MECHANICAL | JUDGMENT | MISS | shipped |
| F-20260820T1816 | render | F | holdout | JUDGMENT | MECHANICAL | MISS | shipped |
| F-20260821T0042 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | shipped |
| F-20260822T1811 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | shipped |
| F-20260826T1827 | render | F | dev | MECHANICAL | MECHANICAL | MATCH | shipped |
| F-20260831T1810 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20260901T0107 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20260902T1803 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20260903T0034 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20260910T1820 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20260913T1816 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20260918T1818 | render | F | holdout | MECHANICAL | JUDGMENT | MISS | withheld |
| F-20260919T1613 | render | F | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| F-20260920T0053 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20260922T1048 | render | F | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| F-20260927T2220 | render | F | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| F-20260928T0042 | render | F | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| F-20261002T2012 | render | F | holdout | JUDGMENT | MECHANICAL | MISS | withheld |
| F-20261004T0104 | render | F | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| F-20261018T1832 | render | F | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| F-20261020T2015 | render | F | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| F-20261021T0101 | render | F | holdout | MECHANICAL | MECHANICAL | MATCH | withheld |
| F-20261023T0024 | render | F | holdout | JUDGMENT | JUDGMENT | MATCH | withheld |
| F-20261025T2043 | render | F | holdout | JUDGMENT | - | PENDING | withheld |
| F-20261026T2219 | render | F | holdout | JUDGMENT | - | PENDING | withheld |
| F-20261029T1851 | render | F | holdout | JUDGMENT | - | PENDING | withheld |
| F-20261030T2003 | render | F | holdout | JUDGMENT | - | PENDING | withheld |

## Summary, holdout only

The gate reads the holdout split, so these match the output of `compare.py scoreboard`, the command that prints agreement and the sequential-test verdict per family, to the digit.

| Family | Scored | Matched | Missed | Pending | SPRT decision |
|---|---|---|---|---|---|
| ops | 62 | 52 | 10 | 8 | CONTINUE (S=-1.90) |
| render | 38 | 26 | 12 | 7 | REJECT (S=-7.36) |
