# Scoreboard demo. Run from shadow-medic: cd shadow-medic && vhs ../tools/demo.tape
Output ../media/scoreboard-demo.gif
Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 21
Set Width 1200
Set Height 460
Set Padding 24
Set Framerate 12
Set TypingSpeed 40ms
Set Theme { "name": "shadow", "black": "#041c1c", "red": "#e06c5a", "green": "#7fc8a0", "yellow": "#C7A96B", "blue": "#6aa6b8", "magenta": "#b48ead", "cyan": "#5fb3b3", "white": "#ffe6cb", "brightBlack": "#2a4a4a", "brightRed": "#e06c5a", "brightGreen": "#7fc8a0", "brightYellow": "#FFBF00", "brightBlue": "#6aa6b8", "brightMagenta": "#b48ead", "brightCyan": "#5fb3b3", "brightWhite": "#ffe6cb", "background": "#041c1c", "foreground": "#ffe6cb", "selection": "#2a4a4a", "cursor": "#FFBF00" }

Hide
Type "export PS1='\[\e[38;2;199;169;107m\]$ \[\e[0m\]' && clear"
Enter
Show

Type "python3 compare.py scoreboard --family ops | grep -E '^(\[holdout\]|SPRT)'"
Enter
Sleep 2.5s
Type "python3 compare.py scoreboard --family render | grep -E '^(\[holdout\]|SPRT)'"
Enter
Sleep 2.5s
Type "python3 compare.py compare cases/F-20260822T1811 results/shadow-F-20260822T1811-*.md"
Enter
Sleep 2.5s
Sleep 3s
