## Creating a new ISO
1. Download the `Install macOs <VERSION>` app
   1. Visit the app store for the os you would like to create an iso for.
      1. [Monterey](https://apps.apple.com/us/app/macos-monterey/id1576738294?mt=12)
      2. [Big Sure](https://apps.apple.com/us/app/macos-big-sur/id1526878132?mt=12)
   2. Click on the link to open in the app store
   3. After it finishes downloading and begins to run, right click on the open app and exit
   4. Note that the app `Install macOs <VERSION>` is now in your applications folder
2. Convert the app to an iso
   1. Run `./create-macos-bootable-for-virtualbox-sh "/Applications/Install macOs <VERSION>"`
      1. Note this is going to do quite a few interactions with `hdiutil` which is quite heavy and may fail. It may be necessary to edit the script at points in order to get it to run correctly.
   2. Note that a new file called `macOSinstaller<TODAYS_DATE>.iso`
   3. Rename the `macOsinstaller<TODAYS_DATE>.iso > <MAC_OS_VERSION>.iso`
   4. Move into the `iso` folder

## Creating a new VM in VirtualBox
1. Create a new VM called `<MAC_OS_VERSION>` and select `OS X` and `OS X (64 bit)` for the other options
   1. Be sure to set the disk memory to 50GB or the installation will fail
   2. Click through all other options (we will modify after creation)
2. Change the following settings
   1. Set System > Motherboard > Base memory: 8192MB. 
   2. Set System > Processor > Processors: 4. 
   3. Set Display > Screen > Video Memory: 128MB.
3. Set the optical drive to the iso for the version of osX you want to create
   1. virtual machine > click on settings > select storage > select the optical drive > browse the installer iso.
4. The VM is ready to start
   1. The VM should open to a terminal screen that is continuously adding text and eventually comes to the apple icon
      1. If you are prompted with a yellow shell prompt, something has gone wrong
5. Select disk utilities and select the disk and format it with the default settings
   1. When installing Monterey installation it is necessary to do the following commands to avoid a boot loop
   ```
      VBoxManage modifyvm 'OS X Monterey' --cpuidset 00000001 000306a9 00020800 80000201 178bfbff
      VBoxManage setextradata 'OS X Monterey' VBoxInternal/TM/TSCMode RealTSCOffset
   ```
6. Start the installer
7. Click though all the setup options
