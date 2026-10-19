<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class Chat extends CI_Controller
{
    public function index()
    {
        $names = array();
        foreach ($this->config->item('atlas_clients') as $id => $client) {
            $names[$id] = $client['name'];
        }
        $this->load->view('chat', array(
            'clients' => $names,
            'current' => $this->currentClient(),
            'csrfName' => $this->security->get_csrf_token_name(),
            'csrfHash' => $this->security->get_csrf_hash(),
            'maxMessage' => $this->config->item('atlas_max_message'),
        ));
    }

    public function send()
    {
        if ($this->input->method() !== 'post') {
            return $this->json(array('message' => 'Method not allowed.'), 405);
        }
        $message = trim((string) $this->input->post('message'));
        if ($message === '' || mb_strlen($message) > $this->config->item('atlas_max_message')) {
            return $this->json(array('message' => 'Please enter a question of up to '.$this->config->item('atlas_max_message').' characters.'), 422);
        }
        $result = $this->atlas_client->chat($this->currentClient(), $message, $this->session->userdata('conversation_id'));
        if (!$result['ok']) {
            return $this->json(array('message' => $this->fallback($result)), $this->failureStatus($result));
        }
        if (!empty($result['data']['conversation_id'])) {
            $this->session->set_userdata('conversation_id', $result['data']['conversation_id']);
        }
        return $this->json(array('data' => $result['data']));
    }

    public function feedback()
    {
        if ($this->input->method() !== 'post') {
            return $this->json(array('message' => 'Method not allowed.'), 405);
        }
        $messageId = (string) $this->input->post('message_id');
        $rating = (string) $this->input->post('rating');
        if (!ctype_digit($messageId) || !in_array($rating, array('up', 'down'), TRUE)) {
            return $this->json(array('message' => 'Invalid feedback.'), 422);
        }
        $result = $this->atlas_client->feedback($this->currentClient(), $messageId, $rating);
        if (!$result['ok']) {
            return $this->json(array('message' => 'Could not save your feedback right now.'), $this->failureStatus($result));
        }
        return $this->json(array('ok' => TRUE));
    }

    public function switch_client()
    {
        $clients = $this->config->item('atlas_clients');
        $id = (string) $this->input->post('client_id');
        if ($this->input->method() === 'post' && isset($clients[$id])) {
            $this->session->set_userdata('client_id', $id);
            $this->session->unset_userdata('conversation_id');
        }
        redirect('/');
    }

    private function currentClient()
    {
        $clients = $this->config->item('atlas_clients');
        $id = $this->session->userdata('client_id');
        return isset($clients[$id]) ? $id : key($clients);
    }

    private function failureStatus(array $result)
    {
        if ($result['error'] === 'timeout') {
            return 504;
        }
        return $result['error'] === 'unreachable' ? 503 : 502;
    }

    private function fallback(array $result)
    {
        if ($result['error'] === 'timeout') {
            return 'The assistant is taking too long to answer. Please try again, or ask to speak to an analyst.';
        }
        if ($result['error'] === 'unreachable') {
            return 'The assistant service is unavailable right now. Please try again shortly.';
        }
        if ($result['status'] === 422) {
            return 'That question could not be processed. Please rephrase it and try again.';
        }
        return 'Something went wrong while answering. Please try again, or ask to speak to an analyst.';
    }

    private function json(array $payload, $status = 200)
    {
        $this->output
            ->set_status_header($status)
            ->set_content_type('application/json', 'utf-8')
            ->set_output(json_encode($payload));
    }
}
