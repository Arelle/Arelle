class XbrlExtractionWorker
  include Shoryuken::Worker

  shoryuken_options queue: 'xbrl_extraction', auto_delete: true

  def perform(sqs_msg, body)
    Shoryuken.logger.info("[XbrlExtractionWorker] Received body #{body.inspect} from message #{sqs_msg.inspect}")

    message_body      = JSON.parse(body, symbolize_names: true)
    extract_from_path = message_body.fetch(:extract_from_path)
    extract_to_path   = message_body.fetch(:extract_to_path)

    system("python3 /opt/arelle/arelleCmdLine.py -f #{extract_from_path} \
      --facts #{extract_to_path} \
      --factListCols \"Label Name contextRef unitRef Dec Prec Lang Value EntityScheme EntityIdentifier Period Dimensions\"")
  end
end
