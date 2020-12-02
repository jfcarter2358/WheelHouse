import utils
import enums

class Interactive:
    def __init__(self, path):
        """ Read in the prompts from the interactive file """
        self.prompts = utils.read_file(path)

    def do_prompt(self):
        """ Ask the user for configuration information """
        # we need _something_ in the dictionary even if the user decides to use all defaults
        # otherwise for some unknown reason it won't work
        user_in = {'__meta__': '__user_input__'}

        print('Please enter the information asked for in the following prompts in order to configure your deployment')
        # get the config information from the user
        for p in self.prompts:
            answer = input(p['prompt'])
            if len(answer.strip()) > 0 and 'variable' in p.keys():
                user_in[p['variable']] = answer

        # return the data
        return user_in
            