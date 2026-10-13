import re, os
txt = open(os.path.expandvars(r'%TEMP%\tapir_commands.js'), encoding='utf-8').read()
names = re.findall(r'"name"\s*:\s*"([A-Za-z]+)"', txt)
seen = []
for n in names:
    if n not in seen:
        seen.append(n)
print(len(seen))
print('\n'.join(seen))
