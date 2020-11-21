
class XbrlExtractionWorker
  include Shoryuken::Worker

  shoryuken_options queue: 'xbrl_extraction', auto_delete: true

  def perform(sqs_msg)
    extract_from_path = sqs_msg[:extract_from_path]
    extract_to_path   = sqs_msg[:extract_to_path]
    system("python3 /opt/arelle/arelleCmdLine.py -f #{extract_from_path} --concepts #{extract_to_path}")
  end
end
