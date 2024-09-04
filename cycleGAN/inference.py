import os
import argparse
from accelerate import Accelerator
import torch
from transformers import PretrainedConfig
from my_utils.training_utils import prepare_formal_natural_inputs, decode_logits_or_inputs
from transformers.modeling_utils import load_sharded_checkpoint
import json
from model_preparation import load_model


def load_model_for_inference(checkpoint_path):
    train_cmdlargs_path = os.path.join(checkpoint_path, 'cmd_args.json')
    with open(train_cmdlargs_path, 'r') as file:
        data = json.load(file)

    wait_token = data.get('wait_tok', '<w>')
    print(f'initializing model. This may take a bit ...')
    nl_init_end_toks = [data['natural_init_tok'], data['natural_end_tok']]
    fl_init_end_toks = [data['formal_init_tok'], data['formal_end_tok']]
    ae_model, tokenizer, wait_id = load_model(data['model_name'], wait_token=wait_token, use_pretrained=False,
                                              use_perplexity_loss=False, use_decoder=data['use_decoder'],
                                              use_encoder=data['use_encoder'], fl_init_end_toks=fl_init_end_toks,
                                              nl_init_end_toks=nl_init_end_toks)
    print(f'Loading model. Also takes a bit ...')
    load_sharded_checkpoint(ae_model, checkpoint_path)

    print('=================Done=================')

    return ae_model, tokenizer, wait_id, fl_init_end_toks, nl_init_end_toks


def generate_text(model, tokenizer, fl_init_end_toks, nl_init_end_toks,
                  natural_texts, max_length, num_beams, do_sample, top_k, top_p):
    # Configure generation parameters
    generation_args = {
        'max_length': max_length,
        'num_beams': num_beams,
        'do_sample': do_sample,
        'top_k': top_k,
        'top_p': top_p,
        'early_stopping': True if num_beams > 1 else False
    }

    natural_texts = nl_init_end_toks[0] + natural_texts + nl_init_end_toks[1] + fl_init_end_toks[0]
    inputs = tokenizer(natural_texts, return_tensors='pt', max_length=1024, truncation=True).to(model.device)

    # Generate output using specified strategy
    with torch.no_grad():
        output = model.generate(**inputs, **generation_args)

    # Decode and return output text
    return tokenizer.decode(output[0], skip_special_tokens=True)


def main():
    parser = argparse.ArgumentParser(description="Generate text from a pretrained model")
    parser.add_argument("-ckpt", "--checkpoint_path", type=str, required=True,
                        help="Path to the DeepSpeed model checkpoint directory")
    # parser.add_argument("--input_text", type=str,
    #                     default='X is a point. BCDE is a trapezoid. Let G, H, F, I be points such that the diagonals '
    #                             'of quadrilateral FGHI are equal. J is a points such that J is on line DA.',
    #                     help="Input text to generate text from")
    parser.add_argument("--input_text", type=str,
                        default='Two circles G1 and G2 intersect at two points M and N. Let AB be the line tangent to '
                                'these circles at A and B, respectively, so that M lies closer to AB than N. Let CD be '
                                'the line parallel to AB and passing through the point M, with C on G1 and D on G2. '
                                'Lines AC and BD meet at E; lines AN and CD meet at P; lines BN and CD meet at Q. '
                                'Show that EP = EQ.',
                        help="Natural language input to be formalized")
    parser.add_argument("--max_length", type=int, default=512, help="Maximum length of the generated text")
    parser.add_argument("--num_beams", type=int, default=1, help="Number of beams for beam search")
    parser.add_argument("--do_sample", action='store_true', help="Enable sampling for generation")
    parser.add_argument("--top_k", type=int, default=0, help="Top-K sampling")
    parser.add_argument("--top_p", type=float, default=0.0, help="Top-P (nucleus) sampling")

    args = parser.parse_args()

    # Initialize Accelerator
    accelerator = Accelerator()

    # Load model
    model, tokenizer, wait_id, fl_init_end_toks, nl_init_end_toks = (
        load_model_for_inference(checkpoint_path=args.checkpoint_path))
    model, tokenizer = accelerator.prepare(model.decoder, tokenizer)

    # Generate text
    generated_text = generate_text(model, tokenizer, fl_init_end_toks, nl_init_end_toks,
                                   args.input_text, args.max_length, args.num_beams, args.do_sample,
                                   args.top_k, args.top_p)
    print(generated_text)


if __name__ == "__main__":
    main()