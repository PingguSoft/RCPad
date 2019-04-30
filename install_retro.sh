## install.sh

sudo pkill -9 -ef RCPad-Pie

sudo cp ./libraspidmx.so.1 /usr/lib

sudo rm -rf /opt/retropie/configs/all/RCPad-Pie/
sudo rm -f ./RCPad-Pie/*.pyc
sudo cp -f -r ./RCPad-Pie /opt/retropie/configs/all/

sudo chmod +x /opt/retropie/configs/all/RCPad-Pie/pngview

#sudo sed -i 's/APP_PATH      = "."/APP_PATH      = "\/opt\/retropie\/configs\/all\/RCPad-Pie"/' /opt/retropie/configs/all/RCPad-Pie/RCPad-Pie.py
sudo sed -i '/RCPad-Pie.py/d' /opt/retropie/configs/all/autostart.sh

sudo sed -i '1i\\/usr/bin/python /opt/retropie/configs/all/RCPad-Pie/RCPad-Pie.py  /dev/input/js0 /dev/ttyACM0 &' /opt/retropie/configs/all/autostart.sh


echo
echo "Setup Completed."
#sleep 3
#sudo reboot
sudo /usr/bin/python /opt/retropie/configs/all/RCPad-Pie/RCPad-Pie.py /dev/input/js0 /dev/ttyACM0 &

