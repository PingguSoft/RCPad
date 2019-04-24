## install.sh

sudo cp ./libraspidmx.so.1 /usr/lib

sudo rm -rf /opt/RCPad-Pie/
sudo cp -f -r ./RCPad-Pie /opt/

sudo chmod +x /opt/RCPad-Pie/pngview

sudo sed -i 's/APP_PATH      = "."/APP_PATH      = "\/opt\/RCPad-Pie"/' /opt/RCPad-Pie/RCPad-Pie.py
sudo sed -i '/RCPad-Pie.py/d' /etc/xdg/lxsession/LXDE-pi/autostart
sudo sed -i '1i\\/usr/bin/python /opt/RCPad-Pie/RCPad-Pie.py  /dev/input/js0 /dev/ttyACM0' /etc/xdg/lxsession/LXDE-pi/autostart
sudo sed -i '/RCPad-Pie.py/d' /etc/rc.local

#sudo sed -i 's/exit 0/\/usr\/bin\/python \/opt\/RCPad-Pie\/RCPad-Pie.py \&\nexit 0/' /etc/rc.local

echo
echo "Setup Completed."
#sleep 3
#sudo reboot
sudo pkill -9 -ef RCPad-Pie
sudo /usr/bin/python /opt/RCPad-Pie/RCPad-Pie.py &
