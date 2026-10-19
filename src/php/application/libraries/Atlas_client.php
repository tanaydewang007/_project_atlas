<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class Atlas_client
{
    private $baseUrl;
    private $timeout;
    private $keys = array();

    public function __construct()
    {
        $ci =& get_instance();
        $this->baseUrl = $ci->config->item('atlas_api_url');
        $this->timeout = $ci->config->item('atlas_timeout');
        foreach ($ci->config->item('atlas_clients') as $id => $client) {
            $this->keys[$id] = $client['key'];
        }
    }

    public function chat($clientId, $message, $conversationId)
    {
        return $this->post('/chat', $clientId, array(
            'client_id' => $clientId,
            'message' => $message,
            'conversation_id' => $conversationId ?: null,
        ));
    }

    public function feedback($clientId, $messageId, $rating)
    {
        return $this->post('/feedback', $clientId, array('message_id' => (int) $messageId, 'rating' => $rating));
    }

    private function post($path, $clientId, array $payload)
    {
        $key = isset($this->keys[$clientId]) ? $this->keys[$clientId] : '';
        $headers = array('Content-Type: application/json');
        if ($key !== '') {
            $headers[] = 'X-API-Key: '.$key;
        }
        $ch = curl_init($this->baseUrl.$path);
        curl_setopt_array($ch, array(
            CURLOPT_POST => TRUE,
            CURLOPT_POSTFIELDS => json_encode($payload),
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_RETURNTRANSFER => TRUE,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_TIMEOUT => $this->timeout,
        ));
        $body = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $errno = curl_errno($ch);
        curl_close($ch);
        if ($errno) {
            return array('ok' => FALSE, 'status' => 0, 'error' => $errno === CURLE_OPERATION_TIMEDOUT ? 'timeout' : 'unreachable');
        }
        $data = json_decode((string) $body, TRUE);
        if ($status < 200 || $status >= 300) {
            return array('ok' => FALSE, 'status' => $status, 'error' => 'upstream');
        }
        return array('ok' => TRUE, 'status' => $status, 'data' => is_array($data) ? $data : array());
    }
}
