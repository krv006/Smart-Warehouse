from rest_framework.serializers import ModelSerializer, ValidationError, SerializerMethodField

from apps.expenses.models import ExpenseType, ExpenseSubType, Expense


class ExpenseSubTypeSerializer(ModelSerializer):
    class Meta:
        model  = ExpenseSubType
        fields = ('id', 'expense_type', 'name')


class ExpenseTypeSerializer(ModelSerializer):
    sub_types = ExpenseSubTypeSerializer(many=True, read_only=True)

    class Meta:
        model  = ExpenseType
        fields = ('id', 'code', 'name', 'sub_types')


class ExpenseSerializer(ModelSerializer):
    expense_type_name = SerializerMethodField()
    sub_type_name     = SerializerMethodField()
    responsible_name  = SerializerMethodField()

    class Meta:
        model  = Expense
        fields = ('id', 'expense_type', 'expense_type_name',
                  'sub_type', 'sub_type_name', 'amount', 'currency',
                  'date', 'responsible', 'responsible_name',
                  'comment', 'attachment', 'created_at')
        read_only_fields = ('created_at',)

    def get_expense_type_name(self, obj):
        return str(obj.expense_type)

    def get_sub_type_name(self, obj):
        return str(obj.sub_type) if obj.sub_type else None

    def get_responsible_name(self, obj):
        return str(obj.responsible) if obj.responsible else None

    def validate(self, attrs):
        expense_type = attrs.get('expense_type',
                                 getattr(self.instance, 'expense_type', None))
        comment = attrs.get('comment', getattr(self.instance, 'comment', None))
        if expense_type and expense_type.code == ExpenseType.OTHER and not comment:
            raise ValidationError(
                {'comment': '"Boshqa" toifasida izoh (comment) majburiy.'}
            )
        return attrs
