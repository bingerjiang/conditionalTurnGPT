import os
import openai
from turngpt.conditional_model import TurnGPT, TurnGPTWandbCallbacks
from transformers import DistilBertModel
from os.path import join
import re
import pdb
from turngpt.plot_utils import plot_trp
import wandb
import torch
import numpy as np
# https://wandb.ai/ivangoncharov/GPT-3%20in%20Python/reports/Use-GPT-3-in-Python-with-the-OpenAI-API-and-W-B-Tables--VmlldzoxOTg4NTMz?galleryTag=nlp

# Load your API key from an environment variable or secret management service
#openai.api_key ="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"

openai.api_key = "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"

prompt = """This is an interview about Dating and relationships.
Interviewer: Where did you go last week?
Response:"""

#"""Response: I went to London.
#Interviewer: How was your trip?"""

response = openai.Completion.create(model="text-davinci-002",
                                    prompt=prompt,
                                    temperature=0.6,
                                    max_tokens=128,)

gpt3_response = response['choices'][0]['text']
#print(response['choices'][0]['text'])
question_list = [
    'What was the most memorable part of your trip?',
    'Why did you choose the destination you did?',
    'How did you plan your trip?',
    'What was your favorite part of the trip?',
    'What was the most challenging part of the trip?',
   # 'What did you learn from your trip?',
    #'What would you do differently next time?',
    'Would you recommend this trip to others?',
    'Did you enjoy it?',
    "I'm sorry to hear that.",
    "I'm glad to hear that.",
    'Go on.',
    'Can you elaborate a bit?']

model_type = 'conditional'
if model_type == 'conditional':
    chpt = join(
       'runs/conditional_turngpt/conditional_turngpt/1w63unay/checkpoints/epoch=6-step=34118.ckpt'
    )
    #27zm0q4e
    # chpt = join(
    #     'runs/conditional_turngpt/conditional_turngpt/27zm0q4e/checkpoints/epoch=9-step=48740.ckpt'
    # ) dont use this, trp_proj has issues, see trp_plots/trp_plots_new_sents/0823_x.png
elif model_type == 'turngpt':
    chpt = join(
        '../TurnGPT/runs/TurnGPT/TurnGPT_2cr6pudn/epoch=10_val_loss=1.7908.ckpt'
    )
model = TurnGPT.load_from_checkpoint(chpt).to("cuda")

sent1 = model.sent_embedding_model
sent2 = DistilBertModel.from_pretrained("distilbert-base-uncased")
pdb.set_trace()

def split_prompt_to_dialog(prompt, sp1, sp2):
    '''
    Convert prompt to a list of utterances
    '''
    dialog = re.split('\n'+sp1+':|\n'+sp2+':',prompt)
    dialog.pop(0)
    if dialog[-1] == '':
        dialog.pop()
    return dialog

def add_next_utt(dialog, question_list):
    dialog_list = []
    for question in question_list:
        new_dialog = dialog.copy()
        new_dialog.append(question)
        dialog_list.append(new_dialog)
        #pdb.set_trace()
    return dialog_list

def get_response_with_max_trp_prob(model, out):
    ts_idx = [(sublist == model.tokenizer.eos_token_id).nonzero(as_tuple=True)[0] for sublist in out['input_ids']]
    start_idx = ts_idx[0][-3]+1
    end_idx = ts_idx[0][-2]+1 ## changed by b2 aug 23: need to +1!
    trp = out['trp_probs'][:, start_idx:end_idx]
    max_trp = torch.max(trp, 1)
    max_trp_idx_batch = torch.max(max_trp.values, 0).indices
    max_trp_idx_seq = max_trp.indices[max_trp_idx_batch] + start_idx
    response_to_add = model.tokenizer.decode(out['input_ids'][max_trp_idx_batch][start_idx:max_trp_idx_seq])
    
    question_to_add = question_list[max_trp_idx_batch]
    print(response_to_add, question_to_add)
    #pdb.set_trace()
    return response_to_add, question_to_add

def get_max_prob_idx (model, out):
    '''
    input: trp proj probs
    output:  0s and 1s
    '''
    return None

turn_list = [
        ['What did you do yesterday?', 'I went hiking with my friends John and Mary. What did you do yesterday?', 'I was painting the wall of my garage.'],
        ['What did you do yesterday?', 'I went hiking with my friends John and Mary.', 'That sounds cool!'],
        #['What did you do yesterday?', 'I went hiking with my friends John and Mary. What did you do yesterday?', 'That sounds cool!'],
        #['What did you do yesterday?', 'I went hiking with my friends John and Mary. What did you do yesterday?', 'Are you okay?'],
        ['What did you order?', 'What we always have for brunch here, tuna sandwiches, fries, pudding, and coffee.', 'That sounds good!'],
       # ['What did you order?', 'What we always have for brunch here, tuna sandwiches, fries, pudding, and coffee.', 'Are you okay?'],
        ['What did you order?', 'What we always have for brunch here, do you want anything else today?', 'No, that sounds good!']
    ]

###############################################
## calcualate accuracy
#out = model.string_list_to_trp(turn_list)
out = model.string_list_to_trp_inputid (turn_list)
#pdb.set_trace()
ts_idx = [(sublist == model.tokenizer.eos_token_id).nonzero(as_tuple=True)[0] for sublist in out['input_ids']]
total_turns = 0
correct_turns = 0

#for b in range(len(ts_idx)):
for b in range(out["trp_proj"].shape[0]):
    dialog_ts = ts_idx[b]
    ith_turn = 0
    while ith_turn < len(dialog_ts)-1:
        if ith_turn == 0:
            start_idx = 0
            end_idx = dialog_ts[ith_turn]+1
        else:
            start_idx = dialog_ts[ith_turn-1]+1
            end_idx = dialog_ts[ith_turn]+1
        trp_proj = out['trp_proj'][b].cpu()
        max_trp_idx = torch.max(trp_proj[start_idx:end_idx],0).indices
        if max_trp_idx == len(trp_proj[start_idx:end_idx])-1:
            correct_turns +=1
        else:
            sentence = model.tokenizer.decode(out['input_ids'][b])
            #pdb.set_trace()
            print('===========')
            print('ith_turn = ', ith_turn)
            
            print(sentence)
            print(max_trp_idx)
            print('===========')
        total_turns +=1
        # pdb.set_trace()
        ith_turn += 1
#####################################

## test which threshold
interval = 0.01
thresholds = np.arange(0, 1, interval)
threshold_results = dict()
for threshold in thresholds:
    threshold_results[threshold] = 0
#thresholds = [0.8, 0.7, 0.6, 0.5]
#threshold_results = {0.5:0, 0.6:0, 0.7:0, 0.8:0}
out = model.string_list_to_trp_inputid (turn_list)
#pdb.set_trace()
ts_idx = [(sublist == model.tokenizer.eos_token_id).nonzero(as_tuple=True)[0] for sublist in out['input_ids']]
#total_turns = 0
#correct_turns = 0

#for b in range(len(ts_idx)):
for b in range(out["trp_proj"].shape[0]):
    for threshold in thresholds:
        dialog_ts = ts_idx[b]
        ith_turn = 0
        while ith_turn < len(dialog_ts)-1:
            if ith_turn == 0:
                start_idx = 0
                end_idx = dialog_ts[ith_turn]+1
            else:
                start_idx = dialog_ts[ith_turn-1]+1
                end_idx = dialog_ts[ith_turn]+1
            trp_proj = out['trp_proj'][b].cpu()
            current_utt = trp_proj[start_idx:end_idx]
            idx_above_threshold = [i for i in range(len(current_utt)) if current_utt[i]>threshold]
            print(idx_above_threshold)
            #pdb.set_trace()
            if len(idx_above_threshold)==1 and idx_above_threshold[0] == len(current_utt)-1:
            ## if only one satisfies and it is the last position where it is the ts
            ## this is the only case it satisfies. add 1
                threshold_results[threshold] += 1
            #max_trp_idx = torch.max(trp_proj[start_idx:end_idx],0).indices
            #max_trp = torch.max(trp_proj[start_idx:end_idx],0).values
            #pdb.set_trace()
            # if max_trp_idx == len(trp_proj[start_idx:end_idx])-1:
            #     correct_turns +=1
            # else:
            #     sentence = model.tokenizer.decode(out['input_ids'][b])
            #     #pdb.set_trace()
            #     print('===========')
            #     print('ith_turn = ', ith_turn)
                
            #     print(sentence)
            #     print(max_trp_idx)
            #     print('===========')
            #total_turns +=1
            # pdb.set_trace()
            ith_turn += 1
best_key = max(threshold_results, key=threshold_results.get)
print(best_key )
print(threshold_results[best_key])
pdb.set_trace()
plot = False
if plot:
    for b in range(out["trp_probs"].shape[0]):
        proj = out["trp_proj"][b].cpu() if "trp_proj" in out else None
        #pdb.set_trace()
        print(proj)
        text = out['tokens'][b]
        #pdb.set_trace()
        text.insert(0, '<nextutt>')
        text.pop()
        fig, _ = plot_trp(
            trp=out["trp_probs"][b].cpu().detach(),
            proj=proj.detach(),
            text=text,
            unk_token=model.tokenizer.unk_token,
            eos_token=model.tokenizer.eos_token,
            plot=True,
        )
       # fig.savefig(f'trp_plots/trp_plots_new_sents/{b}')
        fig.savefig(f'trp_plots/trp_plots_new_sents/0905_1_{b}')
        calc_correct = True

        if calc_correct:
            dialog_ts = ts_idx[b]
            ith_turn = 0
            while ith_turn < len(dialog_ts)-1:
                if ith_turn == 0:
                    start_idx = 0
                    end_idx = dialog_ts[ith_turn]+1
                else:
                    start_idx = dialog_ts[ith_turn-1]+1
                    end_idx = dialog_ts[ith_turn]+1
                
                max_trp_idx = torch.max(proj[start_idx:end_idx],0).indices
                if max_trp_idx == len(proj[start_idx:end_idx])-1:
                    correct_turns +=1
                else:
                    sentence = model.tokenizer.decode(out['input_ids'][b])
                    pdb.set_trace()
                    print('===========')
                    print('ith_turn = ', ith_turn)
                    
                    print(sentence)
                    print(max_trp_idx)
                    print('===========')
                total_turns +=1
                #pdb.set_trace()
                ith_turn += 1
print('total correct = ', correct_turns)
print('total turns = ', total_turns)
#pdb.set_trace()

## a turn: gpt3 generates the answer, and turngpt decides where to take the turn, given all possible questions.
nturns = 3
i = 0
gpt3= False
while i < nturns and gpt3:

    response = openai.Completion.create(model="text-davinci-002",
                                prompt=prompt,
                                temperature=0.6,
                                max_tokens=256,)
    gpt3_response = response['choices'][0]['text']
    print(i)
    print('gpt3_response: ',gpt3_response)
    prompt_new = prompt + gpt3_response+'\nInterviewer:'
    dialog = split_prompt_to_dialog(prompt_new,'Interviewer','Response' )
    # dialog with next question
    dialog_list = add_next_utt(dialog, question_list)
    # output with 
    out = model.string_list_to_trp_inputid(dialog_list)
    response_to_add, question_to_add = get_response_with_max_trp_prob(model, out)
    
    #print('response_to_add: ',response_to_add)
    prompt = prompt + response_to_add + '\nInterviewer:' + question_to_add + '\nResponse:'
    #print('prompt: ',prompt)
    plot = False
    if plot:
        for b in range(out["trp_probs"].shape[0]):
            proj = out["trp_proj"][b].cpu() if "trp_proj" in out else None
            #pdb.set_trace()
            text = out['tokens'][b]
            #pdb.set_trace()
            text.insert(0, '<nextutt>')
            text.pop()
            fig, _ = plot_trp(
                trp=out["trp_probs"][b].cpu(),
                proj=proj,
                text=text,
                unk_token=model.tokenizer.unk_token,
                eos_token=model.tokenizer.eos_token,
                plot=True,
            )
            fig.savefig(f'trp_plots/questions_0718/{b}')
        #pdb.set_trace()
        # model.logger.experiment.log(
        #     data={
        #         f"{name}_{b}": wandb.Image(fig),
        #         #"global_step": trainer.global_step,
        #     },
        # )
        # #pdb.set_trace()
        # plt.close("all")

    i+=1
print(prompt)
#pdb.set_trace()