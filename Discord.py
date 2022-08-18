import discord
from discord.ext import commands, tasks
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
from azure.ai.language.questionanswering import QuestionAnsweringClient, models
import time
from copy import deepcopy
import json
from nltk.corpus import wordnet

credential = AzureKeyCredential('''Your key here''')
endpoint = #Your endpoint here
text_analytics_client = TextAnalyticsClient(endpoint, credential)
question_answering_client = QuestionAnsweringClient(endpoint, credential)

job_q = ["Types of a job", "Responsibilities", "Salary", "Working hours", "What to expect", "Qualifications", "Skills", "Work experience", "Employers", "Professional development", "Career prospects"]
deg_q = ["Job options", "Work experience", "Employers", "Skills", "Further study", "What do the graduates do?"]

job_deg_q = [i for i in job_q if i in deg_q]
job_q = [i for i in job_q if i not in job_deg_q]
deg_q = [i for i in deg_q if i not in job_deg_q]

f = open("job_list.txt")
job_list = f.read().splitlines()
for i in range(len(job_list)):
    job_list[i] = job_list[i].lower()
f.close()
job_dict = dict()
for i in job_list:
    if '/' in i:
        temp = i.split(" ")
        for j in range(len(temp)):
            temp[j] = temp[j].split("/")
        res = []
        for j in temp:
            if len(res) == 0:
                for m in j:
                    res.append(m)
            else:
                tmp = []
                for k in res:
                    for m in j:
                        tmp.append(k + " " + m)
                res = tmp
        for j in res:
            job_dict[j] = i
    else:
        job_dict[i] = i
job_input_syn_dict = dict()
for i in job_dict.keys():
    job = i.replace(" ", "_")
    synonyms = []
    for syn in wordnet.synsets(job):
        for l in syn.lemmas():
            synonyms.append(l.name())
    synonyms = set(synonyms)
    if len(synonyms) == 0:
        job_input_syn_dict[i.replace("_", " ")] = i.replace("_", " ")
    else:
        for j in synonyms:
            job_input_syn_dict[j.replace("_", " ")] = i.replace("_", " ")
print("Job data loaded.")

f = open("degree_list.txt")
degree_list = f.read().splitlines()
for i in range(len(degree_list)):
    degree_list[i] = degree_list[i].lower()
f.close()
degree_dict = dict()
for i in degree_list:
    if 'and' in i:
        temp = i.split(" ")
        index = temp.index("and")
        temp1 = deepcopy(temp)
        temp2 = deepcopy(temp)
        temp1.pop(index)
        temp1.pop(index)
        temp2.pop(index - 1)
        temp2.pop(index - 1)
        deg1 = " ".join(temp1)
        deg2 = " ".join(temp2)
        degree_dict[deg1] = i
        degree_dict[deg2] = i
    degree_dict[i] = i
degree_input_syn_dict = dict()
for i in degree_dict.keys():
    degree = i.replace(" ", "_")
    synonyms = []
    for syn in wordnet.synsets(degree):
        for l in syn.lemmas():
            synonyms.append(l.name())
    synonyms = set(synonyms)
    if len(synonyms) == 0:
        degree_input_syn_dict[i.replace("_", " ")] = i.replace("_", " ")
    else:
        for j in synonyms:
            degree_input_syn_dict[j.replace("_", " ")] = i.replace("_", " ")
print("Degree data loaded.")

userInfoStorage = dict()    #(key:user, value:[job, degree, last_mentioned, last_activate_time])

f = open('qa_database.json', "r", encoding='UTF-8')
qa_database = json.loads(f.read())
f.close()

previous_answer = None
followupQuestion = []

def output_postprocess(output):
    global followupQuestion
    global previous_answer
    best_match = output.answers[0]
    answer = ""
    if best_match.answer == "No answer found":
        answer = "Sorry, I didn't find the answer to your question."
    else:
        try:
            answer = qa_database[best_match.answer]
        except:
            raise Exception()
    previous_answer = best_match
    prompts = best_match.dialog.prompts
    followupQuestion = []
    for i in prompts:
        followupQuestion.append(i.display_text)
    if len(followupQuestion) > 0:
        answer += "\nYou may also be interested in the following topics regarding this subject:\n"
        for i in range(len(followupQuestion)):
            answer += (str(i + 1) + ". " + followupQuestion[i] + "\n")
        answer += "You may input a new question, or choose one of the questions above by typing in the question or the number before it."
    return answer

def userInfoStore(author, job, degree):
    global userInfoStorage
    if not job and not degree: return
    if author in userInfoStorage.keys():
        if job:
            userInfoStorage[author][0] = job
            userInfoStorage[author][2] = 0
        if degree:
            userInfoStorage[author][1] = degree
            userInfoStorage[author][2] = 1
        userInfoStorage[author][3] = time.time()
    else:
        if not job and degree:
            userInfoStorage[author] = [job, degree, 1, time.time()]
        else:
            userInfoStorage[author] = [job, degree, 0, time.time()]

def MessageProcess(author, message):
    global followupQuestion
    global previous_answer
    global job_dict, job_input_syn_dict, degree_dict, degree_input_syn_dict
    output = None
    # Follow up question
    if message in followupQuestion:
        output = question_answering_client.get_answers(question=previous_answer.answer + " " + message, \
            project_name="test", deployment_name="production")
        return output_postprocess(output)
    if message.isdigit():
        if len(followupQuestion) == 0:
            return "Sorry, I can't understand your question."
        if int(message) <= len(followupQuestion):
            print(previous_answer.answer + " " + followupQuestion[int(message) - 1])
            output = question_answering_client.get_answers(question=previous_answer.answer + " " + followupQuestion[int(message) - 1], \
                project_name="test", deployment_name="production")
            print(output.answers[0].answer)
        else:
            return "Invalid choice of number. Please try again."
        return output_postprocess(output)
    followupQuestion = []
    
    # Job or degree mentioned
    key_phrase_doc = text_analytics_client.extract_key_phrases([message])[0]
    if key_phrase_doc.is_error:
        raise Exception("")
    key_phrases = key_phrase_doc.key_phrases
    mentioned_job = None
    mentioned_degree = None
    for key_phrase in key_phrases:
        key_phrase = key_phrase.lower()
        for job in job_input_syn_dict.keys():
            if job in key_phrase:
                if not mentioned_job:
                    mentioned_job = job_dict[job_input_syn_dict[job]]
                else:
                    return "Sorry, could you please simplify your question?"
        for degree in degree_input_syn_dict:
            if degree in key_phrase:
                if not mentioned_degree:
                    mentioned_degree = degree_dict[degree_input_syn_dict[degree]]
                else:
                    return "Sorry, could you please simplify your question?"
    userInfoStore(author, mentioned_job, mentioned_degree)

    # Process question
    output = question_answering_client.get_answers(question=message, project_name="test", deployment_name="production")
    if mentioned_job or mentioned_degree:
        return output_postprocess(output)
    saved_job = None
    saved_degree = None
    try:
        saved_job = userInfoStorage[author][0]
        saved_degree = userInfoStorage[author][1]
    except:
        pass
    if output.answers[0].answer in deg_q:
        if saved_degree:
            message = saved_degree + " " + message
            output = question_answering_client.get_answers(question=message, project_name="test", deployment_name="production")
            return output_postprocess(output)
        else:
            return "I need more information. Could you specify your degree and try again?"
    if output.answers[0].answer in job_q:
        if saved_job:
            message = saved_job + " " + message
            output = question_answering_client.get_answers(question=message, project_name="test", deployment_name="production")
            return output_postprocess(output)
        else:
            return "I need more information. Could you specify your ideal job and try again?"
    if output.answers[0].answer in job_deg_q:
        if saved_degree:
            message = saved_degree + " " + message
            output = question_answering_client.get_answers(question=message, project_name="test", deployment_name="production")
            return output_postprocess(output)
        if saved_job:
            message = saved_job + " " + message
            output = question_answering_client.get_answers(question=message, project_name="test", deployment_name="production")
            return output_postprocess(output)
        else:
            return "I need more information. Could you specify your degree or your ideal job and try again?"
    return output_postprocess(output)

class MyClient(discord.Client, discord.VoiceClient):
    async def on_ready(self):
        print("Ready")
    
    async def on_message(self, message):
        #if message.content == "\checktable":
        #    print(userInfoStorage)
        #    return

        if message.author == self.user:
            return

        #try:
        result = MessageProcess(message.author, message.content)
        #except:
        #    result = "Oops, something went wrong."

        await message.channel.send(result)
    
    @tasks.loop(hours=1)
    async def hourly_database_refresh_schedule():
        #print("Executed")
        for i in list(userInfoStorage):
            if time.time() - userInfoStorage[i][3] > 3600:
                userInfoStorage.pop(i)

    hourly_database_refresh_schedule.start()

client = MyClient()
client.run('''Your Discord API key here''')