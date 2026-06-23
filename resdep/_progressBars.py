"""
Progress bar to print to console in the absence of a GUI
"""


def printProgressBar(
    iteration,
    total,
    prefix="",
    suffix="",
    decimals=1,
    length=100,
    fill="█",
    printEnd="\r",
):
    """
    Call in a loop to create terminal progress bar
    
    Parameters
    ----------
    iteration: int (required)
       current iteration
    total: int (required)
           total iterations
    prefix: str (optional)
        prefix string
    suffix: str (optional)
        suffix string
    decimals: int (optional)
        positive number of decimals in percent complete
    length: int (optional)
        character length of bar
    fill: str (optional)
        bar fill character
    printEnd: str (optional)
        end character (e.g. "\r", "\r\n")
    """
    percent = ("{0:." + str(decimals) + "f}").format(
        100 * (iteration / float(total))
    )
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + "-" * (length - filledLength)
    print(f"\r{prefix}|{bar}| {percent}% {suffix}", end=printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()
