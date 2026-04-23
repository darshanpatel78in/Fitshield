from rest_framework import serializers

class SendOTPSerializer(serializers.Serializer):
    country_code = serializers.CharField(required=False, max_length=5, allow_blank=True)  
    phone_number = serializers.CharField(required=False, max_length=15, allow_blank=True)  
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, data):
        phone_number = data.get('phone_number')
        country_code = data.get('country_code')
        email = data.get('email')

        if not phone_number and not email:
            raise serializers.ValidationError("Either phone_number or email is required.")
        if phone_number and not country_code:
            raise serializers.ValidationError("Country code is required when providing a phone number.")
        return data

