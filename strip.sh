# !sh
#
cpp -D MICROPYTHON -D VT100 -D CONSOLE_IO pye.py | sed "s/\ *#.*$//" | sed "/^$/d" >pye_mp.py
cpp -D MICROPYTHON -D VT100 -D DIRECT_LCD_IO pye.py | sed "s/\ *#.*$//" | sed "/^$/d" >pye_lcd.py
cat shebang <(cpp -D LINUX -D VT100 -D CONSOLE_IO pye.py | sed "s/\ *#.*$//" | sed "/^$/d") >pye
chmod +x pye
mpy-cross -o pye_mp.mpy pye_mp.py
#
