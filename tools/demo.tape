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
Set Theme { "name": "graphite", "black": "#0e1117", "red": "#b5654a", "green": "#4f9a6f", "yellow": "#8b949e", "blue": "#7f9bb8", "magenta": "#8b949e", "cyan": "#7f9bb8", "white": "#e6e9ee", "brightBlack": "#2c333d", "brightRed": "#b5654a", "brightGreen": "#4f9a6f", "brightYellow": "#8b949e", "brightBlue": "#7f9bb8", "brightMagenta": "#8b949e", "brightCyan": "#7f9bb8", "brightWhite": "#e6e9ee", "background": "#0e1117", "foreground": "#e6e9ee", "selection": "#2c333d", "cursor": "#7f9bb8" }

Hide
Type "export PS1='\[\e[38;2;139;148;158m\]$ \[\e[0m\]' && clear"
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
