for text in ["0" + "1" * 4300, "00" + "7" * 4299, "0" * 4301, "0" + "1" * 10]:
    try:
        print(int(text, 0))
    except ValueError as e:
        print("ValueError:", str(e)[:90])
