## install.sh
#sudo pkill -9 -ef RCPad-Pie

sudo cp ./libraspidmx.so.1 /media/pi/EZ_WB_FS/usr/lib

sudo rm -rf /opt/RCPad-Pie/
sudo rm -f ./RCPad-Pie/*.pyc
sudo cp -f -r ./RCPad-Pie /media/pi/EZ_WB_FS/opt/

sudo chmod +x /media/pi/EZ_WB_FS/opt/RCPad-Pie/pngview

sudo sed -i 's/APP_PATH      = "."/APP_PATH      = "\/opt\/RCPad-Pie"/' /media/pi/EZ_WB_FS/opt/RCPad-Pie/RCPad-Pie.py

sudo sed -i '/RCPad-Pie.py/d' /media/pi/EZ_WB_FS/etc/rc.local
sudo sed -i -e 's/^exit 0/sudo \/usr\/bin\/python \/opt\/RCPad-Pie\/RCPad-Pie.py \/dev\/input\/js0 \/dev\/ttyACM0 \&\n&/g' /media/pi/EZ_WB_FS/etc/rc.local

echo
echo "Setup Completed."

