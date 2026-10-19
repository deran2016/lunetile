module Lunetile
  class NetworkError < StandardError
    attr_reader :code, :native_code
    def initialize(code, native_code = 0)
      @code, @native_code = code, native_code
      super("Network #{code} (native error #{native_code})")
    end
  end

  module HTTP
    private_class_method :__start
    OMITTED = Object.new.freeze
    private_constant :OMITTED
    class Response
      attr_reader :status, :headers, :body
      def initialize(status, raw_headers, body)
        @status, @body = status, body.freeze
        @headers = {}
        raw_headers.split("\r\n").drop(1).each do |line|
          name, value = line.split(':', 2)
          next unless value
          (@headers[name.downcase.freeze] ||= []) << value.strip.freeze
        end
        @headers.each_value(&:freeze)
        @headers.freeze
        freeze
      end
      def json
        source = @body.dup.force_encoding(Encoding::UTF_8)
        raise JSON::ParserError, 'Response is not valid UTF-8' unless source.valid_encoding?
        JSON.parse(source, create_additions: false, allow_nan: false, max_nesting: 100)
      rescue JSON::ParserError, JSON::NestingError
        raise JSON::ParserError, 'Invalid JSON response', cause: nil
      end
    end

    class Request
      def initialize(handle)
        @handle = handle
      end
      def state; @handle.state; end
      def done?; state != :pending; end
      def cancel; @handle.cancel; end
      def response
        return nil unless state == :succeeded
        @response ||= Response.new(*@handle.result)
      end
      def error; @handle.error; end
    end

    def self.request(method, url, headers: {}, body: OMITTED, json: OMITTED, timeout_ms: 10_000)
      raise ArgumentError, 'body and json are mutually exclusive' unless body.equal?(OMITTED) || json.equal?(OMITTED)
      method = method.to_s.upcase
      raise ArgumentError, 'Unsupported HTTP method' unless %w[GET POST PUT PATCH DELETE HEAD OPTIONS].include?(method)
      raise TypeError, 'url must be a String' unless url.is_a?(String)
      raise ArgumentError, 'Invalid URL' if url.include?("\0") || url.bytesize > 8192
      raise TypeError, 'headers must be a Hash' unless headers.is_a?(Hash)
      normalized = {}
      headers.each do |name, value|
        unless name.is_a?(String) && name.match?(/\A[!#$%&'*+.^_`|~0-9A-Za-z-]+\z/) && value.is_a?(String) && !value.match?(/[\r\n\x00]/)
          raise ArgumentError, 'Invalid HTTP header'
        end
        key = name.downcase
        raise ArgumentError, 'Reserved or duplicate HTTP header' if %w[host content-length transfer-encoding connection].include?(key) || normalized.key?(key)
        normalized[key] = value
      end
      unless json.equal?(OMITTED)
        body = JSON.generate(json, allow_nan: false, max_nesting: 100)
        normalized['content-type'] ||= 'application/json; charset=utf-8'
      end
      body = ''.b if body.equal?(OMITTED)
      raise TypeError, 'body must be a String' unless body.is_a?(String)
      raise ArgumentError, 'Request body exceeds 1 MiB' if body.bytesize > 1024 * 1024
      lines = normalized.map { |name, value| "#{name}: #{value}\r\n" }.join
      raise ArgumentError, 'Request headers exceed 64 KiB' if lines.bytesize > 65_536
      Request.new(__start(method, url, lines, body, timeout_ms))
    end
  end

  module TCP
    private_class_method :__connect
    def self.connect(host, port, tls: true, timeout_ms: 10_000)
      raise TypeError, 'host must be a String' unless host.is_a?(String)
      raise ArgumentError, 'Invalid host' if host.empty? || host.bytesize > 1024 || host.match?(/[\x00\s\/\\]/)
      raise ArgumentError, 'port must be between 1 and 65535' unless port.is_a?(Integer) && port.between?(1, 65_535)
      raise ArgumentError, 'tls must be true or false' unless tls == true || tls == false
      __connect(host, port, tls, timeout_ms)
    end
  end
end
