import logging
import watchtower

all_logs_path = 'logs/all_logs.log'
error_log_path = 'logs/err_logs.log'

logger_instances = dict({})

class bot_loggers:
  global logger_instances

  logging_on = True # should rarely need to turn this off

  def err_log(message):
    if not bot_loggers.logging_on:
      print(message)
      return
    #err_spec_logger = bot_loggers.setup_logger('err_spec_logger', error_log_path, logging.ERROR)
    err_gene_logger = bot_loggers.setup_logger('err_logger', all_logs_path, logging.ERROR)

    #err_spec_logger.error(message)
    err_gene_logger.error(message)

  def info_log(message):
    if not bot_loggers.logging_on:
      print(message)
      return
    info_logger = bot_loggers.setup_logger('info_logger', all_logs_path, logging.INFO)
    info_logger.info(message)


  def warn_log(message):
    if not bot_loggers.logging_on:
      print(message)
      return
    warn_logger = bot_loggers.setup_logger('warn_logger', all_logs_path, logging.WARNING)
    warn_logger.warning(message)



  def setup_logger(logger_name, logger_file_path, logger_level):
    if logger_name in logger_instances:
      return logger_instances[logger_name]

    logger = logging.getLogger(logger_name)

    formatter = logging.Formatter('%(asctime)s %(levelname)-8s |  %(message)s')
    #fileHandler = logging.FileHandler(logger_file_path, mode = 'a')
    #fileHandler.setFormatter(formatter)

    cw_handler = watchtower.CloudWatchLogHandler(log_group="Omega-Log-Group")
    cw_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.setLevel(logger_level)
    #logger.addHandler(fileHandler)
    logger.addHandler(cw_handler)
    logger.addHandler(console_handler)

    logger_instances[logger_name] = logger

    return logger

