echo $AWS_ACCESS_KEY:$AWS_SECRET_ACCESS_KEY > ${HOME}/.passwd-s3fs
chmod 600 ${HOME}/.passwd-s3fs

s3fs decodeinvesting-s3fs /var/s3fs/ -o passwd_file=${HOME}/.passwd-s3fs #-o dbglevel=info -f -o curldbg

shoryuken -r ./xbrl_extraction_worker.rb -q xbrl_extraction
