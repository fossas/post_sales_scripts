from python.utils import api


def main(api_key):
	group_id = input("Enter the release group ID: ")
	release_id = input("Enter the release ID: ")
	output_format = input("Enter the output format (HTML | MD | PDF | CSV | TXT | SPDX): ")
	preview = True
	email_address = None
	print("Would you like to:\n  1) Preview the report\n  2) Have the report emailed to you")
	_preview = int(input(" > "))
	if _preview == 2:
		preview = False
		email_address = input("Enter your email address: ")

	print(
		api.release_group_attribution_reports(
			group_id, release_id, output_format,
			preview, email_address, api_key=api_key
		)
	)
