from distutils.core import setup
setup(
  name = 'HealthChecker_Server',         # How you named your package folder (MyLib)
  packages = ['HealthChecker_Server'],   # Chose the same as "name"
  version = '0.1.0',      # Start with a small number and increase it with every change you make
  license='MIT',        # Chose a license from here: https://help.github.com/articles/licensing-a-repository
  description = 'A HealthChecker Server',   # Give a short description about your library
  author = 'dWiGhT Mulcahy',                   # Type in your name
  author_email = 'dWiGhTMulcahy@gmail.com',      # Type in your E-Mail
  url = 'https://github.com/dwightmulcahy/healthchecker.server',   # Provide either the link to your github or to your website
  download_url = 'https://github.com/user/reponame/archive/v_01.tar.gz',    # I explain this later on
  keywords = ['HEALTH CHECK', 'MEANINGFULL', 'KEYWORDS'],   # Keywords that define your package best
  install_requires=[            # I get to this in a second
          'validators',
          'beautifulsoup4',
      ],
  classifiers=[
    'Development Status :: 4 - Beta',      # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
    'Intended Audience :: Developers',      # Define that your audience are developers
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: MIT License',   # Again, pick a license
    'Programming Language :: Python :: 3.7',      #Specify which pyhton versions that you want to support
    'Programming Language :: Python :: 3.8',
  ],
)