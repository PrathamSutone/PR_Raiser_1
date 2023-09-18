import pandas as pd, os, time
from utilities.embedding import split_embed
from utilities.create_clone import create_clone
from utilities.files2analyse import files2analyse, check_file_type
from utilities.tokenCount import tokenCount
from utilities.repoutils import select_repo
from utilities.notebook_utils import convert_ipynb_to_python
from utilities.create_project_summary import create_project_summary
from utilities.summarize import summarize_str
from utilities.mixpanel import track_event
from nltk.corpus import stopwords
from utilities.role_analyzer import evaluate_role

def summarize_file(repo_name, filepath, i, userlogger, email):
    full_file_path = os.path.join("../user", email, repo_name, filepath)

    if not check_file_type(full_file_path):
        print("File " + filepath + " was not summarized as it is not a text file")
        p = ("File " + filepath + " was not Analyzed as it is not a text file")
        userlogger.log(p)
        return i, "Ignore"

    i += 1
    p = ("Analyzing " + filepath)
    userlogger.log(p)

    if filepath.endswith(".ipynb"):
        # Convert .ipynb file to human-readable format
        file_contents = convert_ipynb_to_python(full_file_path)
    else:
        with open(full_file_path, 'r') as f:
            try:
                file_contents = f.read()
            except UnicodeDecodeError:
                p = ("File " + filepath + " was not Analyzed as it is not a text file")
                userlogger.log(p)
                return i, "Ignore"

    if tokenCount(file_contents) > 60000:
        p = ("File " + filepath + " was not analyzed as it is too long")
        userlogger.log(p)
        return i, "File content too long"

    return i, summarize_str(filepath, file_contents, email, userlogger)

def train_AI(repo_name, userlogger, email):
    track_event('TrainAI', {'email': email, 'Repo': repo_name})

    fsfilename = "../user/" + email + '/AIFiles/' + repo_name + ".csv"

    file_paths_details = files2analyse(repo_name, email)

    if len(file_paths_details) == 0:
        #create an empty dataframe with filepath, embedding and summary columns
        fs = pd.DataFrame(columns=['file_path', 'embedding', 'summary'])
        fs.to_csv(fsfilename, index=False)
        userlogger.log("This repo is empty, nothing to train")
        return

    fs = pd.DataFrame(file_paths_details)
    fs.columns = ['file_path']
    start_time = time.time()

    i = 0
    fs['summary'] = ''
    fs['embedding'] = ''
    fs['role'] = None
    userlogger.log("Starting analysis", percent="0", time_left="0")

    for ind in fs.index:
        i_new, fs['summary'][ind] = summarize_file(repo_name, fs['file_path'][ind], i, userlogger, email)
        if fs['summary'][ind] != "Ignore":
            fs['embedding'][ind] = split_embed(fs['file_path'][ind]+" "+fs['summary'][ind], email)
        if i_new != i:
            i = i_new
        if i != 0:
            time_elapsed = time.time() - start_time
            p = str(round(100 * (ind + 1) / len(fs)))
            t = str(round(time_elapsed / 60, 2))
            userlogger.clear_logs()
            userlogger.log("",percent=p,time_left=t)

    fs = fs[fs['summary'] != "Ignore"]

    userlogger.log("Analyzed all files successfully")

    fs.to_csv(fsfilename, index=False)
    create_project_summary(repo_name,email)

    userlogger.clear_logs()
    userlogger.log("Evaluating file roles")
    fs = evaluate_role(fs, email, 0, repo_name)

    userlogger.clear_logs()
    userlogger.log("Indexing files")
    start_time = time.time()
    embedding_rate = 600
    stop_words = set(stopwords.words('english'))
    
    delay = 60/embedding_rate
    for ind in fs.index:
        if fs['summary'][ind] != "Ignore":
            filtered_summary = ' '.join([word for word in (fs['file_path'][ind] + fs['role'][ind] + fs['summary'][ind]).split() if word.lower() not in stop_words])
            fs['embedding'][ind] = split_embed(filtered_summary, email)
            time_elapsed = time.time() - start_time
            p = str(round(100 * (ind + 1) / len(fs)))
            t = str(round(time_elapsed / 60, 2))
            time.sleep(delay)
            userlogger.clear_logs()
            userlogger.log("Indexing :"+fs['file_path'][ind],percent=p,time_left=t)

    userlogger.clear_logs()
    userlogger.log("Indexed all files successfully")

    fs.to_csv(fsfilename, index=False)

    select_repo(repo_name,email)
    print("100% Done")
    create_clone(repo_name, email)
    userlogger.clear_logs()
    userlogger.log("Your repo was trained into the AI successfully")
    time.sleep(2)
    userlogger.clear_logs() 