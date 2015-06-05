# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'CreditRequestStatus'
        db.create_table('credit_creditrequeststatus', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('request', self.gf('django.db.models.fields.related.ForeignKey')(related_name='statuses', to=orm['credit.CreditRequest'])),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('credit', ['CreditRequestStatus'])

        # Adding model 'CreditRequest'
        db.create_table('credit_creditrequest', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('model_utils.fields.AutoCreatedField')(default=datetime.datetime.now)),
            ('modified', self.gf('model_utils.fields.AutoLastModifiedField')(default=datetime.datetime.now)),
            ('uuid', self.gf('django.db.models.fields.CharField')(unique=True, max_length=32, db_index=True)),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('course', self.gf('django.db.models.fields.related.ForeignKey')(related_name='credit_requests', to=orm['credit.CreditCourse'])),
            ('provider', self.gf('django.db.models.fields.related.ForeignKey')(related_name='credit_requests', to=orm['credit.CreditProvider'])),
            ('parameters', self.gf('jsonfield.fields.JSONField')()),
        ))
        db.send_create_signal('credit', ['CreditRequest'])

        # Adding unique constraint on 'CreditRequest', fields ['username', 'course', 'provider']
        db.create_unique('credit_creditrequest', ['username', 'course_id', 'provider_id'])

        # Adding M2M table for field providers on 'CreditCourse'
        m2m_table_name = db.shorten_name('credit_creditcourse_providers')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('creditcourse', models.ForeignKey(orm['credit.creditcourse'], null=False)),
            ('creditprovider', models.ForeignKey(orm['credit.creditprovider'], null=False))
        ))
        db.create_unique(m2m_table_name, ['creditcourse_id', 'creditprovider_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'CreditRequest', fields ['username', 'course', 'provider']
        db.delete_unique('credit_creditrequest', ['username', 'course_id', 'provider_id'])

        # Deleting model 'CreditRequestStatus'
        db.delete_table('credit_creditrequeststatus')

        # Deleting model 'CreditRequest'
        db.delete_table('credit_creditrequest')

        # Removing M2M table for field providers on 'CreditCourse'
        db.delete_table(db.shorten_name('credit_creditcourse_providers'))


    models = {
        'credit.creditcourse': {
            'Meta': {'object_name': 'CreditCourse'},
            'course_key': ('xmodule_django.models.CourseKeyField', [], {'unique': 'True', 'max_length': '255', 'db_index': 'True'}),
            'enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'providers': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['credit.CreditProvider']", 'symmetrical': 'False'})
        },
        'credit.crediteligibility': {
            'Meta': {'unique_together': "(('username', 'course'),)", 'object_name': 'CreditEligibility'},
            'course': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'eligibilities'", 'to': "orm['credit.CreditCourse']"}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'eligibilities'", 'to': "orm['credit.CreditProvider']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        },
        'credit.creditprovider': {
            'Meta': {'object_name': 'CreditProvider'},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'provider_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255', 'db_index': 'True'})
        },
        'credit.creditrequest': {
            'Meta': {'unique_together': "(('username', 'course', 'provider'),)", 'object_name': 'CreditRequest'},
            'course': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'credit_requests'", 'to': "orm['credit.CreditCourse']"}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'parameters': ('jsonfield.fields.JSONField', [], {}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'credit_requests'", 'to': "orm['credit.CreditProvider']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32', 'db_index': 'True'})
        },
        'credit.creditrequeststatus': {
            'Meta': {'object_name': 'CreditRequestStatus'},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'request': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'statuses'", 'to': "orm['credit.CreditRequest']"}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'credit.creditrequirement': {
            'Meta': {'unique_together': "(('namespace', 'name', 'course'),)", 'object_name': 'CreditRequirement'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'course': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'credit_requirements'", 'to': "orm['credit.CreditCourse']"}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'criteria': ('jsonfield.fields.JSONField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'namespace': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'credit.creditrequirementstatus': {
            'Meta': {'object_name': 'CreditRequirementStatus'},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'reason': ('jsonfield.fields.JSONField', [], {'default': '{}'}),
            'requirement': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'statuses'", 'to': "orm['credit.CreditRequirement']"}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'})
        }
    }

    complete_apps = ['credit']
