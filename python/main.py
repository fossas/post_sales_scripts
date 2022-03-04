from utils import api, scripts as _scripts  # type: ignore


def main():
	print('Thanks for using the FOSSA post sales scripts!')
	api_key = api.get_api_key()
	scripts = _scripts.get_scripts()
	# print(scripts)
	print('So, what would you like to do today?')
	for key, script in enumerate(scripts):
		print(f'{key + 1}) {script["name"]}')
		# print(script)
	choice = int(input('> '))
	chosen_func = scripts[choice - 1]['function']
	chosen_func(api_key)


if __name__ == '__main__':
	main()
