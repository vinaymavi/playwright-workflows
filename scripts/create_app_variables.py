import argparse
import re

from prefect.variables import Variable


parser = argparse.ArgumentParser(description="Create WhatsApp application variables in Prefect.")
parser.add_argument("whatsapp_phone_number_id", nargs="?", default="1335092943031361", help="WhatsApp Business phone number ID")
parser.add_argument("whatsapp_api_version", nargs="?", default="v25.0", help="Graph API version (default: v25.0)")
parser.add_argument("--overwrite", action="store_true", help="Update existing variables")
args = parser.parse_args()

if not args.whatsapp_phone_number_id.isdigit():
    parser.error("whatsapp_phone_number_id must contain only digits")
if not re.fullmatch(r"v\d+\.\d+", args.whatsapp_api_version):
    parser.error("whatsapp_api_version must look like v25.0")

Variable.set("whatsapp_phone_number_id", args.whatsapp_phone_number_id, overwrite=args.overwrite)
Variable.set("whatsapp_api_version", args.whatsapp_api_version, overwrite=args.overwrite)
print("WhatsApp application variables saved.")
