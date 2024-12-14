from ScriptManager import ScriptManager

sm = ScriptManager(language='en')
sm.transcribe('test.mp4')
sm.print_script()
sm.save_script_file('test_script_file.txt')
print(sm.script_detected_in(12, 12.1))
print(sm.get_script_by_time(99))